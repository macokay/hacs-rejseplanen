"""DataUpdateCoordinator for Rejseplanen."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    BASE_URL,
    CONF_SCAN_INTERVAL,
    CONF_STATION_ID,
    CONF_STATIONS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_DEPARTURES,
)

_LOGGER = logging.getLogger(__name__)


class RejseplanenCoordinator(DataUpdateCoordinator[dict]):
    """Fetches departure data for all configured stations."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self._entry = entry
        self.api_key: str = entry.data["api_key"]

        scan_interval = int(
            entry.options.get(
                CONF_SCAN_INTERVAL,
                entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            )
        )

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=scan_interval),
        )

    @property
    def stations(self) -> list[dict]:
        return self._entry.options.get(
            CONF_STATIONS,
            self._entry.data.get(CONF_STATIONS, []),
        )

    async def _async_update_data(self) -> dict:
        """Fetch departure boards for all stations. Returns {unique_key: [departures]}."""
        session = async_get_clientsession(self.hass)
        data: dict = {}

        # Group by station_id — only one API call per physical station
        station_ids: dict[str, list[dict]] = {}
        for station in self.stations:
            sid = station[CONF_STATION_ID]
            station_ids.setdefault(sid, []).append(station)

        for station_id, configs in station_ids.items():
            try:
                async with asyncio.timeout(10):
                    async with session.get(
                        f"{BASE_URL}/departureBoard",
                        params={
                            "id": station_id,
                            "format": "json",
                            "accessId": self.api_key,
                            "maxJourneys": MAX_DEPARTURES * 3,  # fetch more to allow filtering
                        },
                    ) as resp:
                        if resp.status != 200:
                            _LOGGER.warning(
                                "API returned %s for station %s", resp.status, station_id
                            )
                            for cfg in configs:
                                data[_station_key(cfg)] = []
                            continue

                        payload = await resp.json(content_type=None)
                        all_departures = _parse_departures(payload)

                        # Store filtered result for each sensor config of this station
                        for cfg in configs:
                            data[_station_key(cfg)] = _apply_filters(all_departures, cfg)

            except asyncio.TimeoutError:
                _LOGGER.warning("Timeout fetching departures for station %s", station_id)
                for cfg in configs:
                    data[_station_key(cfg)] = []
            except Exception as err:  # noqa: BLE001
                _LOGGER.error("Error fetching departures for station %s: %s", station_id, err)
                for cfg in configs:
                    data[_station_key(cfg)] = []

        if not data and self.stations:
            raise UpdateFailed("All station fetches failed")

        return data


def _station_key(station: dict) -> str:
    """Unique key for a sensor config — station_id + optional filters."""
    from .const import CONF_DIRECTION_FILTER, CONF_TYPE_FILTER, CONF_STATION_ID
    parts = [station[CONF_STATION_ID]]
    d = station.get(CONF_DIRECTION_FILTER, "")
    if d:
        parts.append(d)
    t = station.get(CONF_TYPE_FILTER, [])
    if t:
        parts.append(",".join(sorted(t)))
    return "|".join(parts)


def _apply_filters(departures: list[dict], cfg: dict) -> list[dict]:
    """Filter departures by direction and/or transport type."""
    from .const import CONF_DIRECTION_FILTER, CONF_TYPE_FILTER, MAX_DEPARTURES
    direction = cfg.get(CONF_DIRECTION_FILTER, "").lower()
    types = [t.lower() for t in cfg.get(CONF_TYPE_FILTER, [])]

    result = []
    for dep in departures:
        if direction and direction not in dep.get("direction", "").lower():
            continue
        if types:
            dep_name = dep.get("line", "").lower()
            dep_cat = dep.get("category", "").lower()
            if not any(t in dep_name or t in dep_cat for t in types):
                continue
        result.append(dep)
        if len(result) >= MAX_DEPARTURES:
            break

    return result


def _parse_departures(payload: dict) -> list[dict]:
    """Parse HAFAS DepartureBoard JSON response into a clean list."""
    # API 2.0: Departure is at root level
    raw = payload.get("Departure", [])
    if not raw:
        raw = payload.get("DepartureBoard", {}).get("Departure", [])
    if not raw:
        return []

    if isinstance(raw, dict):
        raw = [raw]

    departures = []
    for dep in raw:
        # Extract category from Product or name prefix
        name = dep.get("name", "")
        cat = ""
        products = dep.get("Product", [])
        if isinstance(products, dict):
            products = [products]
        if products:
            cat = products[0].get("catOut", "")

        departures.append(
            {
                "line": name,
                "category": cat,
                "direction": dep.get("direction", ""),
                "stop": dep.get("stop", ""),
                "type": dep.get("type", ""),
                "platform": dep.get("rtTrack", dep.get("track", dep.get("platform", ""))),
                "scheduled_time": dep.get("time", ""),
                "scheduled_date": dep.get("date", ""),
                "realtime_time": dep.get("rtTime", dep.get("time", "")),
                "realtime_date": dep.get("rtDate", dep.get("date", "")),
                "cancelled": dep.get("cancelled", False),
            }
        )

    return departures

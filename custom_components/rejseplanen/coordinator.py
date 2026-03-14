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
        """Return current station list, preferring options over initial data."""
        return self._entry.options.get(
            CONF_STATIONS,
            self._entry.data.get(CONF_STATIONS, []),
        )

    async def _async_update_data(self) -> dict:
        """Fetch departure boards for all stations. Returns {station_id: [departures]}."""
        session = async_get_clientsession(self.hass)
        data: dict = {}

        for station in self.stations:
            station_id = station[CONF_STATION_ID]
            try:
                async with asyncio.timeout(10):
                    async with session.get(
                        f"{BASE_URL}/departureBoard",
                        params={
                            "id": station_id,
                            "format": "json",
                            "accessId": self.api_key,
                            "maxJourneys": MAX_DEPARTURES,
                        },
                    ) as resp:
                        if resp.status != 200:
                            _LOGGER.warning(
                                "API returned %s for station %s", resp.status, station_id
                            )
                            data[station_id] = []
                            continue

                        payload = await resp.json(content_type=None)
                        _LOGGER.warning("Rejseplanen departureBoard raw keys for %s: %s", station_id, list(payload.keys()))
                        data[station_id] = _parse_departures(payload)

            except asyncio.TimeoutError:
                _LOGGER.warning("Timeout fetching departures for station %s", station_id)
                data[station_id] = []
            except Exception as err:  # noqa: BLE001
                _LOGGER.error(
                    "Error fetching departures for station %s: %s", station_id, err
                )
                data[station_id] = []

        if not data and self.stations:
            raise UpdateFailed("All station fetches failed")

        return data


def _parse_departures(payload: dict) -> list[dict]:
    """Parse HAFAS DepartureBoard JSON response into a clean list."""
    # API 2.0: Departure is at root level, not wrapped in DepartureBoard
    raw = payload.get("Departure", [])
    if not raw:
        # Fallback: old-style wrapper
        raw = payload.get("DepartureBoard", {}).get("Departure", [])
    if not raw:
        return []

    # API returns a dict (not list) when there is only one departure
    if isinstance(raw, dict):
        raw = [raw]

    departures = []
    for dep in raw:
        departures.append(
            {
                "line": dep.get("name", ""),
                "direction": dep.get("direction", ""),
                "stop": dep.get("stop", ""),
                "type": dep.get("type", ""),
                "platform": dep.get("rtTrack", dep.get("track", dep.get("platform", ""))),
                # Scheduled
                "scheduled_time": dep.get("time", ""),
                "scheduled_date": dep.get("date", ""),
                # Realtime — falls back to scheduled if missing
                "realtime_time": dep.get("rtTime", dep.get("time", "")),
                "realtime_date": dep.get("rtDate", dep.get("date", "")),
                "cancelled": dep.get("cancelled", False),
            }
        )

    return departures

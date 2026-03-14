"""Config flow for Rejseplanen."""
from __future__ import annotations

import asyncio
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    BASE_URL,
    CONF_API_KEY,
    CONF_DIRECTION_FILTER,
    CONF_SCAN_INTERVAL,
    CONF_STATION_ID,
    CONF_STATION_NAME,
    CONF_STATIONS,
    CONF_TYPE_FILTER,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_DEPARTURES,
    MAX_STATIONS,
    TRANSPORT_TYPES,
)

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared API helpers
# ---------------------------------------------------------------------------

async def _search_stations(hass: HomeAssistant, api_key: str, query: str) -> list[dict]:
    """Search for stop locations by name."""
    session = async_get_clientsession(hass)
    try:
        async with asyncio.timeout(10):
            async with session.get(
                f"{BASE_URL}/location.name",
                params={"input": query, "format": "json", "accessId": api_key},
            ) as resp:
                if resp.status != 200:
                    return []
                import json as _json
                data = _json.loads(await resp.text())
                raw_list = data.get("stopLocationOrCoordLocation", [])
                return [item["StopLocation"] for item in raw_list if "StopLocation" in item][:10]
    except Exception as err:
        _LOGGER.warning("Rejseplanen _search_stations exception: %s", err)
        return []


async def _fetch_directions(hass: HomeAssistant, api_key: str, station_id: str, type_filter: list[str]) -> list[str]:
    """Fetch departure board and return unique directions, optionally filtered by type."""
    session = async_get_clientsession(hass)
    try:
        async with asyncio.timeout(10):
            async with session.get(
                f"{BASE_URL}/departureBoard",
                params={
                    "id": station_id,
                    "format": "json",
                    "accessId": api_key,
                    "maxJourneys": MAX_DEPARTURES * 3,
                },
            ) as resp:
                if resp.status != 200:
                    return []
                import json as _json
                payload = _json.loads(await resp.text())
                raw = payload.get("Departure", [])
                if isinstance(raw, dict):
                    raw = [raw]

                types_lower = [t.lower() for t in type_filter]
                seen: set[str] = set()
                directions: list[str] = []
                for dep in raw:
                    # Type filter
                    if types_lower:
                        name = dep.get("name", "").lower()
                        products = dep.get("Product", [])
                        if isinstance(products, dict):
                            products = [products]
                        cat = products[0].get("catOut", "").lower() if products else ""
                        if not any(t in name or t in cat for t in types_lower):
                            continue
                    direction = dep.get("direction", "").strip()
                    if direction and direction not in seen:
                        seen.add(direction)
                        directions.append(direction)
                return directions
    except Exception as err:
        _LOGGER.warning("Rejseplanen _fetch_directions exception: %s", err)
        return []


async def _validate_api_key(hass: HomeAssistant, api_key: str) -> bool:
    results = await _search_stations(hass, api_key, "København H")
    return results is not None


def _station_label(station: dict) -> str:
    label = station[CONF_STATION_NAME]
    direction = station.get(CONF_DIRECTION_FILTER, "")
    types = station.get(CONF_TYPE_FILTER, [])
    if direction:
        label += f" → {direction}"
    if types:
        label += f" ({', '.join(types)})"
    return label


# ---------------------------------------------------------------------------
# Config flow
# ---------------------------------------------------------------------------

class RejseplanenConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._api_key: str = ""
        self._scan_interval: int = DEFAULT_SCAN_INTERVAL
        self._stations: list[dict] = []
        self._search_results: list[dict] = []
        self._pending_station: dict = {}
        self._available_directions: list[str] = []

    async def async_step_user(self, user_input: dict | None = None):
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")
        errors: dict = {}
        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            if await _validate_api_key(self.hass, api_key):
                self._api_key = api_key
                self._scan_interval = int(user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
                return await self.async_step_add_station()
            errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_API_KEY): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                ),
                vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=5, max=60, step=5, mode=selector.NumberSelectorMode.SLIDER)
                ),
            }),
            errors=errors,
        )

    async def async_step_add_station(self, user_input: dict | None = None):
        errors: dict = {}
        if user_input is not None:
            results = await _search_stations(self.hass, self._api_key, user_input["station_search"].strip())
            if results:
                self._search_results = results
                return await self.async_step_select_station()
            errors["base"] = "no_stations_found"
        return self.async_show_form(
            step_id="add_station",
            data_schema=vol.Schema({vol.Required("station_search"): selector.TextSelector()}),
            errors=errors,
        )

    async def async_step_select_station(self, user_input: dict | None = None):
        if user_input is not None:
            for result in self._search_results:
                if str(result.get("id", "")) == user_input["station"]:
                    self._pending_station = {
                        CONF_STATION_ID: user_input["station"],
                        CONF_STATION_NAME: result["name"],
                    }
                    break
            return await self.async_step_select_type()
        options = [
            selector.SelectOptionDict(value=str(r["id"]), label=r["name"])
            for r in self._search_results
        ]
        return self.async_show_form(
            step_id="select_station",
            data_schema=vol.Schema({
                vol.Required("station"): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=options)
                )
            }),
        )

    async def async_step_select_type(self, user_input: dict | None = None):
        if user_input is not None:
            types = user_input.get(CONF_TYPE_FILTER, [])
            if types:
                self._pending_station[CONF_TYPE_FILTER] = types
            # Fetch directions based on chosen types
            self._available_directions = await _fetch_directions(
                self.hass,
                self._api_key,
                self._pending_station[CONF_STATION_ID],
                types,
            )
            return await self.async_step_select_direction()
        type_options = [selector.SelectOptionDict(value=t, label=t) for t in TRANSPORT_TYPES]
        return self.async_show_form(
            step_id="select_type",
            data_schema=vol.Schema({
                vol.Optional(CONF_TYPE_FILTER, default=[]): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=type_options, multiple=True)
                ),
            }),
            description_placeholders={"station": self._pending_station.get(CONF_STATION_NAME, "")},
        )

    async def async_step_select_direction(self, user_input: dict | None = None):
        if user_input is not None:
            direction = user_input.get(CONF_DIRECTION_FILTER, "")
            if direction and direction != "__all__":
                self._pending_station[CONF_DIRECTION_FILTER] = direction
            self._stations.append(self._pending_station)
            self._pending_station = {}
            return await self.async_step_add_more()

        dir_options = [selector.SelectOptionDict(value="__all__", label="Alle retninger")]
        dir_options += [
            selector.SelectOptionDict(value=d, label=d)
            for d in self._available_directions
        ]
        return self.async_show_form(
            step_id="select_direction",
            data_schema=vol.Schema({
                vol.Required(CONF_DIRECTION_FILTER, default="__all__"): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=dir_options)
                ),
            }),
            description_placeholders={"station": self._pending_station.get(CONF_STATION_NAME, "")},
        )

    async def async_step_add_more(self, user_input: dict | None = None):
        if user_input is not None:
            if user_input.get("add_more") and len(self._stations) < MAX_STATIONS:
                return await self.async_step_add_station()
            return self.async_create_entry(
                title="Rejseplanen",
                data={
                    CONF_API_KEY: self._api_key,
                    CONF_SCAN_INTERVAL: self._scan_interval,
                    CONF_STATIONS: self._stations,
                },
            )
        at_limit = len(self._stations) >= MAX_STATIONS
        stations_list = ", ".join(_station_label(s) for s in self._stations)
        schema = vol.Schema(
            {vol.Required("add_more", default=False): selector.BooleanSelector()}
        ) if not at_limit else vol.Schema({})
        return self.async_show_form(
            step_id="add_more",
            data_schema=schema,
            description_placeholders={"stations": stations_list, "max": str(MAX_STATIONS), "count": str(len(self._stations))},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return RejseplanenOptionsFlow(config_entry)


# ---------------------------------------------------------------------------
# Options flow
# ---------------------------------------------------------------------------

class RejseplanenOptionsFlow(config_entries.OptionsFlow):

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry
        self._stations: list[dict] = list(
            config_entry.options.get(CONF_STATIONS, config_entry.data.get(CONF_STATIONS, []))
        )
        self._scan_interval: int = int(
            config_entry.options.get(
                CONF_SCAN_INTERVAL,
                config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            )
        )
        self._search_results: list[dict] = []
        self._pending_station: dict = {}
        self._available_directions: list[str] = []

    async def async_step_init(self, user_input: dict | None = None):
        if user_input is not None:
            action = user_input.get("action")
            if action == "add":
                return await self.async_step_add_station()
            if action == "remove":
                return await self.async_step_remove_station()
            if action == "interval":
                return await self.async_step_update_interval()
            return self._save_options()

        at_limit = len(self._stations) >= MAX_STATIONS
        stations_list = ", ".join(_station_label(s) for s in self._stations) or "Ingen"
        action_options = []
        if not at_limit:
            action_options.append(selector.SelectOptionDict(value="add", label="Tilføj sensor"))
        action_options += [
            selector.SelectOptionDict(value="remove", label="Fjern sensor"),
            selector.SelectOptionDict(value="interval", label="Ændr opdateringsinterval"),
            selector.SelectOptionDict(value="save", label="Gem og luk"),
        ]
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required("action"): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=action_options)
                )
            }),
            description_placeholders={"stations": stations_list, "interval": str(self._scan_interval), "max": str(MAX_STATIONS), "count": str(len(self._stations))},
        )

    async def async_step_add_station(self, user_input: dict | None = None):
        errors: dict = {}
        api_key = self._config_entry.data[CONF_API_KEY]
        if user_input is not None:
            results = await _search_stations(self.hass, api_key, user_input["station_search"].strip())
            if results:
                self._search_results = results
                return await self.async_step_select_station()
            errors["base"] = "no_stations_found"
        return self.async_show_form(
            step_id="add_station",
            data_schema=vol.Schema({vol.Required("station_search"): selector.TextSelector()}),
            errors=errors,
        )

    async def async_step_select_station(self, user_input: dict | None = None):
        if user_input is not None:
            for result in self._search_results:
                if str(result.get("id", "")) == user_input["station"]:
                    self._pending_station = {
                        CONF_STATION_ID: user_input["station"],
                        CONF_STATION_NAME: result["name"],
                    }
                    break
            return await self.async_step_select_type()
        options = [
            selector.SelectOptionDict(value=str(r["id"]), label=r["name"])
            for r in self._search_results
        ]
        return self.async_show_form(
            step_id="select_station",
            data_schema=vol.Schema({
                vol.Required("station"): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=options)
                )
            }),
        )

    async def async_step_select_type(self, user_input: dict | None = None):
        if user_input is not None:
            types = user_input.get(CONF_TYPE_FILTER, [])
            if types:
                self._pending_station[CONF_TYPE_FILTER] = types
            api_key = self._config_entry.data[CONF_API_KEY]
            self._available_directions = await _fetch_directions(
                self.hass, api_key, self._pending_station[CONF_STATION_ID], types
            )
            return await self.async_step_select_direction()
        type_options = [selector.SelectOptionDict(value=t, label=t) for t in TRANSPORT_TYPES]
        return self.async_show_form(
            step_id="select_type",
            data_schema=vol.Schema({
                vol.Optional(CONF_TYPE_FILTER, default=[]): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=type_options, multiple=True)
                ),
            }),
            description_placeholders={"station": self._pending_station.get(CONF_STATION_NAME, "")},
        )

    async def async_step_select_direction(self, user_input: dict | None = None):
        if user_input is not None:
            direction = user_input.get(CONF_DIRECTION_FILTER, "")
            if direction and direction != "__all__":
                self._pending_station[CONF_DIRECTION_FILTER] = direction
            self._stations.append(self._pending_station)
            self._pending_station = {}
            return await self.async_step_init()

        dir_options = [selector.SelectOptionDict(value="__all__", label="Alle retninger")]
        dir_options += [
            selector.SelectOptionDict(value=d, label=d)
            for d in self._available_directions
        ]
        return self.async_show_form(
            step_id="select_direction",
            data_schema=vol.Schema({
                vol.Required(CONF_DIRECTION_FILTER, default="__all__"): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=dir_options)
                ),
            }),
            description_placeholders={"station": self._pending_station.get(CONF_STATION_NAME, "")},
        )

    async def async_step_remove_station(self, user_input: dict | None = None):
        if user_input is not None:
            ids_to_remove = set(user_input.get("stations_to_remove", []))
            self._stations = [s for i, s in enumerate(self._stations) if str(i) not in ids_to_remove]
            return await self.async_step_init()
        options = [
            selector.SelectOptionDict(value=str(i), label=_station_label(s))
            for i, s in enumerate(self._stations)
        ]
        return self.async_show_form(
            step_id="remove_station",
            data_schema=vol.Schema({
                vol.Required("stations_to_remove"): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=options, multiple=True)
                )
            }),
        )

    async def async_step_update_interval(self, user_input: dict | None = None):
        if user_input is not None:
            self._scan_interval = int(user_input[CONF_SCAN_INTERVAL])
            return await self.async_step_init()
        return self.async_show_form(
            step_id="update_interval",
            data_schema=vol.Schema({
                vol.Required(CONF_SCAN_INTERVAL, default=self._scan_interval): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=5, max=60, step=5, mode=selector.NumberSelectorMode.SLIDER)
                )
            }),
        )

    def _save_options(self):
        return self.async_create_entry(title="", data={
            CONF_STATIONS: self._stations,
            CONF_SCAN_INTERVAL: self._scan_interval,
        })

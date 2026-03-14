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
    MAX_STATIONS,
    TRANSPORT_TYPES,
)

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared API helpers
# ---------------------------------------------------------------------------

async def _search_stations(hass: HomeAssistant, api_key: str, query: str) -> list[dict]:
    """Search for stop locations by name. Returns up to 10 results."""
    session = async_get_clientsession(hass)
    try:
        async with asyncio.timeout(10):
            async with session.get(
                f"{BASE_URL}/location.name",
                params={"input": query, "format": "json", "accessId": api_key},
            ) as resp:
                _LOGGER.warning(
                    "Rejseplanen location.name status=%s url=%s",
                    resp.status,
                    str(resp.url),
                )
                if resp.status != 200:
                    _LOGGER.warning("Rejseplanen location.name returned HTTP %s", resp.status)
                    return []
                raw_text = await resp.text()
                _LOGGER.warning("Rejseplanen location.name raw response: %.1000s", raw_text)
                import json as _json
                data = _json.loads(raw_text)
                # API 2.0: results are under "stopLocationOrCoordLocation" as a list
                # Each item is {"StopLocation": {...}} or {"CoordLocation": {...}}
                raw_list = data.get("stopLocationOrCoordLocation", [])
                stops = [
                    item["StopLocation"]
                    for item in raw_list
                    if "StopLocation" in item
                ]
                _LOGGER.warning("Rejseplanen stops parsed: %s", stops)
                return stops[:10]
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Rejseplanen _search_stations exception: %s", err)
        return []


async def _validate_api_key(hass: HomeAssistant, api_key: str) -> bool:
    """Validate key by making a cheap location search. Returns True on success."""
    try:
        results = await _search_stations(hass, api_key, "København H")
        return results is not None
    except Exception:  # noqa: BLE001
        return False


def _station_label(station: dict) -> str:
    """Human-readable label for a configured station entry."""
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
    """Handle initial setup: API key -> search station -> select -> filters -> add more?"""

    VERSION = 1

    def __init__(self) -> None:
        self._api_key: str = ""
        self._scan_interval: int = DEFAULT_SCAN_INTERVAL
        self._stations: list[dict] = []
        self._search_results: list[dict] = []
        self._pending_station: dict = {}

    # -- Step 1: API key + interval ----------------------------------------

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
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): selector.TextSelector(
                        selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                    ),
                    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=5, max=60, step=5, mode=selector.NumberSelectorMode.SLIDER)
                    ),
                }
            ),
            errors=errors,
        )

    # -- Step 2: Search station --------------------------------------------

    async def async_step_add_station(self, user_input: dict | None = None):
        errors: dict = {}

        if user_input is not None:
            query = user_input["station_search"].strip()
            results = await _search_stations(self.hass, self._api_key, query)
            if results:
                self._search_results = results
                return await self.async_step_select_station()
            errors["base"] = "no_stations_found"

        return self.async_show_form(
            step_id="add_station",
            data_schema=vol.Schema(
                {vol.Required("station_search"): selector.TextSelector()}
            ),
            errors=errors,
        )

    # -- Step 3: Select from results ---------------------------------------

    async def async_step_select_station(self, user_input: dict | None = None):
        if user_input is not None:
            selected_id = user_input["station"]
            for result in self._search_results:
                if str(result.get("id", "")) == selected_id:
                    self._pending_station = {
                        CONF_STATION_ID: selected_id,
                        CONF_STATION_NAME: result["name"],
                    }
                    break
            return await self.async_step_station_filters()

        options = [
            selector.SelectOptionDict(value=str(r["id"]), label=r["name"])
            for r in self._search_results
        ]
        return self.async_show_form(
            step_id="select_station",
            data_schema=vol.Schema(
                {
                    vol.Required("station"): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=options)
                    )
                }
            ),
        )

    # -- Step 4: Optional filters ------------------------------------------

    async def async_step_station_filters(self, user_input: dict | None = None):
        if user_input is not None:
            direction = user_input.get(CONF_DIRECTION_FILTER, "").strip()
            types = user_input.get(CONF_TYPE_FILTER, [])
            if direction:
                self._pending_station[CONF_DIRECTION_FILTER] = direction
            if types:
                self._pending_station[CONF_TYPE_FILTER] = types

            station_key = (
                self._pending_station[CONF_STATION_ID],
                self._pending_station.get(CONF_DIRECTION_FILTER, ""),
                tuple(sorted(self._pending_station.get(CONF_TYPE_FILTER, []))),
            )
            if station_key not in {
                (s[CONF_STATION_ID], s.get(CONF_DIRECTION_FILTER, ""), tuple(sorted(s.get(CONF_TYPE_FILTER, []))))
                for s in self._stations
            }:
                self._stations.append(self._pending_station)
            self._pending_station = {}
            return await self.async_step_add_more()

        type_options = [
            selector.SelectOptionDict(value=t, label=t) for t in TRANSPORT_TYPES
        ]
        return self.async_show_form(
            step_id="station_filters",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_DIRECTION_FILTER, default=""): selector.TextSelector(
                        selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
                    ),
                    vol.Optional(CONF_TYPE_FILTER, default=[]): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=type_options, multiple=True)
                    ),
                }
            ),
            description_placeholders={"station": self._pending_station.get(CONF_STATION_NAME, "")},
        )

    # -- Step 5: Add another or finish ------------------------------------

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
            description_placeholders={
                "stations": stations_list,
                "max": str(MAX_STATIONS),
                "count": str(len(self._stations)),
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return RejseplanenOptionsFlow(config_entry)


# ---------------------------------------------------------------------------
# Options flow
# ---------------------------------------------------------------------------

class RejseplanenOptionsFlow(config_entries.OptionsFlow):
    """Manage stations and scan interval after initial setup."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry
        self._stations: list[dict] = list(
            config_entry.options.get(
                CONF_STATIONS, config_entry.data.get(CONF_STATIONS, [])
            )
        )
        self._scan_interval: int = int(
            config_entry.options.get(
                CONF_SCAN_INTERVAL,
                config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            )
        )
        self._search_results: list[dict] = []
        self._pending_station: dict = {}

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
        stations_list = (
            ", ".join(_station_label(s) for s in self._stations) or "Ingen"
        )

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
            data_schema=vol.Schema(
                {
                    vol.Required("action"): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=action_options)
                    )
                }
            ),
            description_placeholders={
                "stations": stations_list,
                "interval": str(self._scan_interval),
                "max": str(MAX_STATIONS),
                "count": str(len(self._stations)),
            },
        )

    async def async_step_add_station(self, user_input: dict | None = None):
        errors: dict = {}
        api_key = self._config_entry.data[CONF_API_KEY]

        if user_input is not None:
            query = user_input["station_search"].strip()
            results = await _search_stations(self.hass, api_key, query)
            if results:
                self._search_results = results
                return await self.async_step_select_station()
            errors["base"] = "no_stations_found"

        return self.async_show_form(
            step_id="add_station",
            data_schema=vol.Schema(
                {vol.Required("station_search"): selector.TextSelector()}
            ),
            errors=errors,
        )

    async def async_step_select_station(self, user_input: dict | None = None):
        if user_input is not None:
            selected_id = user_input["station"]
            for result in self._search_results:
                if str(result.get("id", "")) == selected_id:
                    self._pending_station = {
                        CONF_STATION_ID: selected_id,
                        CONF_STATION_NAME: result["name"],
                    }
                    break
            return await self.async_step_station_filters()

        options = [
            selector.SelectOptionDict(value=str(r["id"]), label=r["name"])
            for r in self._search_results
        ]
        return self.async_show_form(
            step_id="select_station",
            data_schema=vol.Schema(
                {
                    vol.Required("station"): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=options)
                    )
                }
            ),
        )

    async def async_step_station_filters(self, user_input: dict | None = None):
        if user_input is not None:
            direction = user_input.get(CONF_DIRECTION_FILTER, "").strip()
            types = user_input.get(CONF_TYPE_FILTER, [])
            if direction:
                self._pending_station[CONF_DIRECTION_FILTER] = direction
            if types:
                self._pending_station[CONF_TYPE_FILTER] = types
            self._stations.append(self._pending_station)
            self._pending_station = {}
            return await self.async_step_init()

        type_options = [
            selector.SelectOptionDict(value=t, label=t) for t in TRANSPORT_TYPES
        ]
        return self.async_show_form(
            step_id="station_filters",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_DIRECTION_FILTER, default=""): selector.TextSelector(
                        selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
                    ),
                    vol.Optional(CONF_TYPE_FILTER, default=[]): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=type_options, multiple=True)
                    ),
                }
            ),
            description_placeholders={"station": self._pending_station.get(CONF_STATION_NAME, "")},
        )

    async def async_step_remove_station(self, user_input: dict | None = None):
        if user_input is not None:
            ids_to_remove = set(user_input.get("stations_to_remove", []))
            self._stations = [
                s for i, s in enumerate(self._stations) if str(i) not in ids_to_remove
            ]
            return await self.async_step_init()

        options = [
            selector.SelectOptionDict(value=str(i), label=_station_label(s))
            for i, s in enumerate(self._stations)
        ]
        return self.async_show_form(
            step_id="remove_station",
            data_schema=vol.Schema(
                {
                    vol.Required("stations_to_remove"): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=options, multiple=True)
                    )
                }
            ),
        )

    async def async_step_update_interval(self, user_input: dict | None = None):
        if user_input is not None:
            self._scan_interval = int(user_input[CONF_SCAN_INTERVAL])
            return await self.async_step_init()

        return self.async_show_form(
            step_id="update_interval",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SCAN_INTERVAL, default=self._scan_interval): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=5, max=60, step=5, mode=selector.NumberSelectorMode.SLIDER
                        )
                    )
                }
            ),
        )

    def _save_options(self):
        return self.async_create_entry(
            title="",
            data={
                CONF_STATIONS: self._stations,
                CONF_SCAN_INTERVAL: self._scan_interval,
            },
        )

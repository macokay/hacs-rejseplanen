"""Sensor platform for Rejseplanen — one sensor per configured station/filter combo."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_DIRECTION_FILTER,
    CONF_STATION_ID,
    CONF_STATION_NAME,
    CONF_STATIONS,
    CONF_TYPE_FILTER,
    DOMAIN,
)
from .coordinator import RejseplanenCoordinator, _station_key


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: RejseplanenCoordinator = hass.data[DOMAIN][entry.entry_id]
    stations = entry.options.get(CONF_STATIONS, entry.data.get(CONF_STATIONS, []))
    async_add_entities(
        RejseplanenDepartureSensor(coordinator, station) for station in stations
    )


class RejseplanenDepartureSensor(CoordinatorEntity[RejseplanenCoordinator], SensorEntity):
    """Shows the next departure from a station/direction/type as state."""

    _attr_icon = "mdi:train"
    _attr_should_poll = False

    def __init__(self, coordinator: RejseplanenCoordinator, station: dict) -> None:
        super().__init__(coordinator)
        self._station = station
        self._key = _station_key(station)
        self._attr_unique_id = f"rejseplanen_{self._key}"
        self._attr_name = self._build_name()

    def _build_name(self) -> str:
        name = f"Rejseplanen {self._station[CONF_STATION_NAME]}"
        direction = self._station.get(CONF_DIRECTION_FILTER, "")
        types = self._station.get(CONF_TYPE_FILTER, [])
        if direction:
            name += f" → {direction}"
        if types:
            name += f" ({', '.join(types)})"
        return name

    @property
    def native_value(self) -> str | None:
        departures = self._departures
        if not departures:
            return None
        return departures[0].get("realtime_time") or departures[0].get("scheduled_time")

    @property
    def extra_state_attributes(self) -> dict:
        departures = self._departures
        return {
            "station": self._station[CONF_STATION_NAME],
            "station_id": self._station[CONF_STATION_ID],
            "direction_filter": self._station.get(CONF_DIRECTION_FILTER, ""),
            "type_filter": self._station.get(CONF_TYPE_FILTER, []),
            "next_departure": departures[0] if departures else None,
            "departures": departures,
        }

    @property
    def available(self) -> bool:
        return (
            super().available
            and self.coordinator.data is not None
            and self._key in self.coordinator.data
        )

    @property
    def _departures(self) -> list[dict]:
        if self.coordinator.data is None:
            return []
        return self.coordinator.data.get(self._key, [])

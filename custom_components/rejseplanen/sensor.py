"""Sensor platform for Rejseplanen — one sensor per configured station."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_STATION_ID, CONF_STATION_NAME, CONF_STATIONS, DOMAIN
from .coordinator import RejseplanenCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up one sensor per station."""
    coordinator: RejseplanenCoordinator = hass.data[DOMAIN][entry.entry_id]
    stations = entry.options.get(CONF_STATIONS, entry.data.get(CONF_STATIONS, []))

    async_add_entities(
        RejseplanenDepartureSensor(coordinator, station) for station in stations
    )


class RejseplanenDepartureSensor(CoordinatorEntity[RejseplanenCoordinator], SensorEntity):
    """Shows the next departure from a station as state; full board in attributes."""

    _attr_icon = "mdi:train"
    _attr_should_poll = False

    def __init__(self, coordinator: RejseplanenCoordinator, station: dict) -> None:
        super().__init__(coordinator)
        self._station_id: str = station[CONF_STATION_ID]
        self._station_name: str = station[CONF_STATION_NAME]
        self._attr_unique_id = f"rejseplanen_{self._station_id}"
        self._attr_name = f"Rejseplanen {self._station_name}"

    @property
    def native_value(self) -> str | None:
        """Return realtime time of next departure, e.g. '14:32'."""
        departures = self._departures
        if not departures:
            return None
        return departures[0].get("realtime_time") or departures[0].get("scheduled_time")

    @property
    def extra_state_attributes(self) -> dict:
        """Return full departure board and station meta."""
        departures = self._departures
        return {
            "station": self._station_name,
            "station_id": self._station_id,
            "next_departure": departures[0] if departures else None,
            "departures": departures,
        }

    @property
    def available(self) -> bool:
        """Mark unavailable if coordinator has no data for this station."""
        return (
            super().available
            and self.coordinator.data is not None
            # Station key present = at least one successful poll
            and self._station_id in self.coordinator.data
        )

    @property
    def _departures(self) -> list[dict]:
        if self.coordinator.data is None:
            return []
        return self.coordinator.data.get(self._station_id, [])

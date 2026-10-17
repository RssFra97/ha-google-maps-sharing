"""Tracker GPS per ogni persona che condivide la posizione."""

from __future__ import annotations

from typing import Any

from locationsharinglib import Person

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.const import ATTR_BATTERY_CHARGING, ATTR_BATTERY_LEVEL, ATTR_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import GoogleMapsConfigEntry
from .const import (
    ATTR_ADDRESS,
    ATTR_FULL_NAME,
    ATTR_LAST_SEEN,
    ATTR_NICKNAME,
    CONF_MAX_GPS_ACCURACY,
    DEFAULT_MAX_GPS_ACCURACY,
    DOMAIN,
)
from .coordinator import GoogleMapsCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GoogleMapsConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Crea un tracker per ogni persona, anche per quelle che compaiono dopo."""
    coordinator = entry.runtime_data
    known: set[str] = set()

    @callback
    def _add_new() -> None:
        new = [pid for pid in (coordinator.data or {}) if pid not in known]
        if new:
            known.update(new)
            async_add_entities(GoogleMapsTracker(coordinator, pid) for pid in new)

    _add_new()
    entry.async_on_unload(coordinator.async_add_listener(_add_new))


class GoogleMapsTracker(CoordinatorEntity[GoogleMapsCoordinator], TrackerEntity):
    """Posizione di una persona da Google Maps."""

    def __init__(self, coordinator: GoogleMapsCoordinator, person_id: str) -> None:
        """Inizializza il tracker."""
        super().__init__(coordinator)
        self._person_id = person_id
        self._person: Person | None = None
        self._attr_unique_id = f"{DOMAIN}_{person_id}"
        self._accept(coordinator.data.get(person_id))
        p = self._person or coordinator.data.get(person_id)
        self._attr_name = (p.full_name or p.nickname) if p else person_id
        # l'account usato per l'accesso di solito non serve: disattivato di default
        self._attr_entity_registry_enabled_default = person_id != coordinator.client.email

    def _accept(self, person: Person | None) -> None:
        """Usa il dato solo se abbastanza preciso e non più vecchio dell'ultimo."""
        if person is None or person.latitude is None:
            return
        max_acc = self.coordinator.config_entry.options.get(
            CONF_MAX_GPS_ACCURACY, DEFAULT_MAX_GPS_ACCURACY
        )
        if max_acc and person.accuracy is not None and person.accuracy > max_acc:
            return
        if (
            self._person is not None
            and person.datetime is not None
            and self._person.datetime is not None
            and person.datetime < self._person.datetime
        ):
            return
        self._person = person

    @callback
    def _handle_coordinator_update(self) -> None:
        self._accept((self.coordinator.data or {}).get(self._person_id))
        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        """Disponibile se Google risponde e c'è almeno una posizione valida."""
        return super().available and self._person is not None

    @property
    def source_type(self) -> SourceType:
        """Sorgente GPS."""
        return SourceType.GPS

    @property
    def latitude(self) -> float | None:
        """Latitudine."""
        return self._person.latitude if self._person else None

    @property
    def longitude(self) -> float | None:
        """Longitudine."""
        return self._person.longitude if self._person else None

    @property
    def location_accuracy(self) -> float:
        """Precisione in metri."""
        return float(self._person.accuracy or 0) if self._person else 0

    @property
    def entity_picture(self) -> str | None:
        """Foto del profilo Google."""
        return self._person.picture_url if self._person else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Indirizzo, ultimo aggiornamento e batteria."""
        p = self._person
        if p is None:
            return {}
        return {
            ATTR_ADDRESS: p.address,
            ATTR_FULL_NAME: p.full_name,
            ATTR_ID: p.id,
            ATTR_LAST_SEEN: dt_util.as_utc(p.datetime).isoformat() if p.datetime else None,
            ATTR_NICKNAME: p.nickname,
            ATTR_BATTERY_CHARGING: p.charging,
            ATTR_BATTERY_LEVEL: p.battery_level,
        }

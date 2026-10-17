"""Sensore di problema: la sessione Google non funziona."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import GoogleMapsConfigEntry
from .coordinator import GoogleMapsCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GoogleMapsConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Aggiunge il sensore della sessione."""
    async_add_entities([GoogleMapsSessionSensor(entry.runtime_data)])


class GoogleMapsSessionSensor(CoordinatorEntity[GoogleMapsCoordinator], BinarySensorEntity):
    """Acceso quando Google Maps non risponde o i cookie sono scaduti."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_name = "Google Maps sessione"
    _attr_icon = "mdi:google-maps"

    def __init__(self, coordinator: GoogleMapsCoordinator) -> None:
        """Inizializza il sensore."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_session"

    @property
    def available(self) -> bool:
        """Sempre disponibile: deve segnalare proprio i guasti."""
        return True

    @property
    def is_on(self) -> bool:
        """Problema se l'ultimo aggiornamento è fallito."""
        return not self.coordinator.last_update_success

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Dettagli su errori e rinnovo dei cookie."""
        c = self.coordinator
        return {
            "ultimo_errore": None if c.last_update_success else str(c.last_exception),
            "ultimo_rinnovo_cookie": c.last_rotation.isoformat() if c.last_rotation else None,
            "rinnovo_riuscito": c.last_rotation_ok,
            "ultimo_salvataggio_cookie": (
                c.last_cookie_save.isoformat() if c.last_cookie_save else None
            ),
            # dati grezzi di Google, anche quando il tracker li scarta per la precisione
            "posizioni_google": c.raw,
        }

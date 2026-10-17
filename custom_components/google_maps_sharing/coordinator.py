"""Coordinatore degli aggiornamenti di Google Maps."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging

from locationsharinglib import Person

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import GoogleMapsApiError, GoogleMapsAuthError, GoogleMapsClient
from .const import (
    CONF_ROTATE_COOKIES,
    DEFAULT_ROTATE_COOKIES,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    ROTATE_INTERVAL,
    SAVE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class GoogleMapsCoordinator(DataUpdateCoordinator[dict[str, Person]]):
    """Legge le posizioni e tiene vivi i cookie."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: GoogleMapsClient) -> None:
        """Inizializza il coordinatore."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )
        self.client = client
        self.last_rotation: datetime | None = None
        self.last_rotation_ok: bool | None = None
        self.last_cookie_save: datetime | None = None
        self.raw: dict[str, dict] = {}

    async def _async_update_data(self) -> dict[str, Person]:
        try:
            people = await self.hass.async_add_executor_job(self.client.fetch)
        except GoogleMapsAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except GoogleMapsApiError as err:
            raise UpdateFailed(str(err)) from err

        self.raw = {
            (p.full_name or pid): {
                "precisione_m": p.accuracy,
                "ultima_posizione": p.datetime.isoformat() if p.datetime else None,
            }
            for pid, p in people.items()
        }

        now = dt_util.utcnow()
        rotated = False
        if self.config_entry.options.get(CONF_ROTATE_COOKIES, DEFAULT_ROTATE_COOKIES) and (
            self.last_rotation is None or now - self.last_rotation >= ROTATE_INTERVAL
        ):
            self.last_rotation = now
            self.last_rotation_ok = await self.hass.async_add_executor_job(self.client.rotate)
            rotated = True

        # Google cambia qualche cookie a ogni risposta: salvo dopo un rinnovo
        # o al massimo ogni SAVE_INTERVAL, per non riscrivere il file ogni minuto.
        if rotated or self.last_cookie_save is None or now - self.last_cookie_save >= SAVE_INTERVAL:
            try:
                if await self.hass.async_add_executor_job(self.client.save_if_changed):
                    self.last_cookie_save = now
            except OSError as err:
                _LOGGER.warning("Impossibile salvare i cookie: %s", err)

        return people

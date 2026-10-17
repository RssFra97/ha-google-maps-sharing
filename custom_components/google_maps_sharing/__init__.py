"""Google Maps (condivisione posizione): sostituto moderno di google_maps."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.util import slugify

from .api import GoogleMapsAuthError, GoogleMapsClient
from .const import COOKIE_FILE
from .coordinator import GoogleMapsCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.DEVICE_TRACKER]

type GoogleMapsConfigEntry = ConfigEntry[GoogleMapsCoordinator]


def cookie_path(hass: HomeAssistant, email: str, template: str = COOKIE_FILE) -> str:
    """Percorso del file dei cookie per un account."""
    return hass.config.path(template.format(slug=slugify(email)))


async def async_setup_entry(hass: HomeAssistant, entry: GoogleMapsConfigEntry) -> bool:
    """Configura l'integrazione da una config entry."""
    email = entry.data[CONF_USERNAME]
    try:
        client = await hass.async_add_executor_job(
            GoogleMapsClient, cookie_path(hass, email), email
        )
    except (GoogleMapsAuthError, OSError) as err:
        raise ConfigEntryAuthFailed(f"Cookie non validi o mancanti: {err}") from err

    coordinator = GoogleMapsCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def _async_options_updated(hass: HomeAssistant, entry: GoogleMapsConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: GoogleMapsConfigEntry) -> bool:
    """Scarica la config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

"""Configurazione da interfaccia di Google Maps (condivisione posizione)."""

from __future__ import annotations

from collections.abc import Mapping
import logging
import os
from typing import Any

try:
    import probatio as vol
except ImportError:  # versioni di HA che usano ancora voluptuous
    import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_SCAN_INTERVAL, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from . import cookie_path
from .api import GoogleMapsApiError, GoogleMapsAuthError, GoogleMapsClient
from .const import (
    CONF_COOKIES,
    CONF_MAX_GPS_ACCURACY,
    CONF_ROTATE_COOKIES,
    DEFAULT_MAX_GPS_ACCURACY,
    DEFAULT_ROTATE_COOKIES,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LEGACY_COOKIE_FILE,
)

_LOGGER = logging.getLogger(__name__)

COOKIES_SELECTOR = TextSelector(TextSelectorConfig(multiline=True))


async def _async_validate(hass: HomeAssistant, email: str, cookie_text: str) -> dict[str, str]:
    """Prova i cookie (incollati, già salvati o del vecchio google_maps) e li salva."""
    path = cookie_path(hass, email)

    def _check() -> None:
        text = cookie_text.strip() or None
        if text is None and not os.path.exists(path):
            legacy = cookie_path(hass, email, LEGACY_COOKIE_FILE)
            if not os.path.exists(legacy):
                raise FileNotFoundError(path)
            with open(legacy, encoding="utf-8") as fh:
                text = fh.read()
        client = GoogleMapsClient(path, email, text)
        client.fetch()
        client.save_if_changed()

    try:
        await hass.async_add_executor_job(_check)
    except GoogleMapsAuthError as err:
        _LOGGER.warning("Verifica dei cookie non riuscita: %s", err)
        return {"base": "invalid_cookies"}
    except FileNotFoundError:
        return {"base": "no_cookies"}
    except GoogleMapsApiError as err:
        _LOGGER.warning("Google Maps non raggiungibile: %s", err)
        return {"base": "cannot_connect"}
    except Exception:
        _LOGGER.exception("Errore imprevisto durante la verifica dei cookie")
        return {"base": "unknown"}
    return {}


class GoogleMapsSharingConfigFlow(ConfigFlow, domain=DOMAIN):
    """Flusso di configurazione."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Account Google e cookie."""
        errors: dict[str, str] = {}
        if user_input is not None:
            email = user_input[CONF_USERNAME].strip().lower()
            await self.async_set_unique_id(email)
            self._abort_if_unique_id_configured()
            errors = await _async_validate(self.hass, email, user_input.get(CONF_COOKIES, ""))
            if not errors:
                return self.async_create_entry(title=email, data={CONF_USERNAME: email})

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.EMAIL)
                    ),
                    vol.Optional(CONF_COOKIES, default=""): COOKIES_SELECTOR,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """Sessione scaduta: chiede nuovi cookie."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Incolla i nuovi cookie (o lascia vuoto per rileggere il file)."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await _async_validate(
                self.hass, entry.data[CONF_USERNAME], user_input.get(CONF_COOKIES, "")
            )
            if not errors:
                return self.async_update_reload_and_abort(entry)

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Optional(CONF_COOKIES, default=""): COOKIES_SELECTOR}),
            description_placeholders={"account": entry.data[CONF_USERNAME]},
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Opzioni."""
        return GoogleMapsSharingOptionsFlow()


class GoogleMapsSharingOptionsFlow(OptionsFlow):
    """Intervallo, precisione minima e rinnovo dei cookie."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Unico passo delle opzioni."""
        if user_input is not None:
            user_input[CONF_SCAN_INTERVAL] = int(user_input[CONF_SCAN_INTERVAL])
            user_input[CONF_MAX_GPS_ACCURACY] = int(user_input[CONF_MAX_GPS_ACCURACY])
            return self.async_create_entry(data=user_input)

        opts = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=opts.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ): NumberSelector(
                        NumberSelectorConfig(min=30, max=900, step=10, unit_of_measurement="s",
                                             mode=NumberSelectorMode.BOX)
                    ),
                    vol.Required(
                        CONF_MAX_GPS_ACCURACY,
                        default=opts.get(CONF_MAX_GPS_ACCURACY, DEFAULT_MAX_GPS_ACCURACY),
                    ): NumberSelector(
                        NumberSelectorConfig(min=10, max=100000, step=10, unit_of_measurement="m",
                                             mode=NumberSelectorMode.BOX)
                    ),
                    vol.Required(
                        CONF_ROTATE_COOKIES,
                        default=opts.get(CONF_ROTATE_COOKIES, DEFAULT_ROTATE_COOKIES),
                    ): BooleanSelector(),
                }
            ),
        )

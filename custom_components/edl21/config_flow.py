"""Config flow for EDL21 integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_SCAN_INTERVAL,
    CONF_SERIAL_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TITLE,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SERIAL_PORT): str,
    }
)


def _options_schema(current: int) -> vol.Schema:
    """Build the options-flow schema with ``current`` as the default."""
    return vol.Schema(
        {
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=current,
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=MIN_SCAN_INTERVAL,
                    max=MAX_SCAN_INTERVAL,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="s",
                )
            ),
        }
    )


class EDL21ConfigFlow(ConfigFlow, domain=DOMAIN):
    """EDL21 config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user setup step."""
        if user_input is not None:
            self._async_abort_entries_match(
                {CONF_SERIAL_PORT: user_input[CONF_SERIAL_PORT]}
            )

            return self.async_create_entry(
                title=DEFAULT_TITLE,
                data=user_input,
                options={CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL},
            )

        data_schema = self.add_suggested_values_to_schema(DATA_SCHEMA, user_input)
        return self.async_show_form(step_id="user", data_schema=data_schema)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow for this handler."""
        return EDL21OptionsFlow(config_entry)


class EDL21OptionsFlow(OptionsFlow):
    """Options flow exposing the scan interval."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Store the entry on a private attribute.

        HA 2024.12+ auto-populates ``self.config_entry`` on the
        OptionsFlow instance, and explicitly assigning it there emits
        a deprecation warning. Older HA releases don't auto-populate
        anything, so we keep our own reference under a different name.
        ``super().__init__()`` is required so HA's framework setup
        (including the auto-populate hook) still runs.
        """
        super().__init__()
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the options-flow init step."""
        if user_input is not None:
            # NumberSelector hands back floats; normalise to int seconds
            # before persisting so downstream code can treat the value
            # uniformly.
            return self.async_create_entry(
                title="",
                data={CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL])},
            )

        current = int(
            self._config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        return self.async_show_form(
            step_id="init", data_schema=_options_schema(current)
        )

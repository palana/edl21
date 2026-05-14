"""The edl21 custom integration.

This integration is a drop-in replacement for the core ``edl21`` component
with three differences:

1. It swaps ``pyserial-asyncio-fast`` (pulled in transitively by pysml)
   for `serialx <https://github.com/puddly/serialx>`_ via
   ``serialx.patch_pyserial()``.
2. It exposes a configurable scan interval through the options flow
   (default 10 s; minimum 1 s) instead of the hard-coded 60 s entity
   update throttle.
3. It applies a runtime patch to ``pysml.asyncio.SmlSerialProtocol``
   that bounds the receive buffer and forces a reconnect on a stuck
   parser — workaround for
   `home-assistant/core#169980
   <https://github.com/home-assistant/core/issues/169980>`_.
"""

from __future__ import annotations

# IMPORTANT: ``serialx.patch_pyserial()`` has to run before anything
# in this process imports ``sml.asyncio`` (which transitively imports
# ``serial_asyncio_fast``). Running it at module-top guarantees that
# Home Assistant's platform loader sees a patched ``serial_asyncio``
# by the time it imports ``.sensor`` below.
import serialx

serialx.patch_pyserial()

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import LOGGER
from .pysml_patch import install_pysml_buffer_patch

PLATFORMS = [Platform.SENSOR]

_PATCHES_INSTALLED = False


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up EDL21 integration from a config entry."""
    global _PATCHES_INSTALLED
    if not _PATCHES_INSTALLED:
        # Apply the pysml.asyncio.SmlSerialProtocol buffer fix. The
        # import inside install_pysml_buffer_patch may block briefly
        # while pysml is loaded for the first time, so it runs in the
        # executor.
        installed = await hass.async_add_executor_job(install_pysml_buffer_patch)
        if installed:
            LOGGER.info(
                "pysml buffer patch installed (workaround for HA core #169980)"
            )
        _PATCHES_INSTALLED = True

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    # Reload the entry whenever its options change so the new scan
    # interval propagates to existing entities.
    config_entry.async_on_unload(
        config_entry.add_update_listener(_async_options_updated)
    )
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)


async def _async_options_updated(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Reload the entry when its options change."""
    await hass.config_entries.async_reload(config_entry.entry_id)

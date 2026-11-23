"""LessRecords: guarded label-specific Recorder retention."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .manager import LessRecordsManager, get_settings, normalize_run_time
from .policy import PolicyError, validate_policies

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up an entry; do not initiate any purge on startup."""
    settings = get_settings(entry)
    try:
        validate_policies(settings["policies"])
        normalize_run_time(settings["run_time"])
    except (KeyError, PolicyError) as err:
        _LOGGER.error("LessRecords setup refused invalid configuration: %s", err)
        return False

    manager = LessRecordsManager(hass, entry)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = manager
    manager.async_start()
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload after a deliberate configuration change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the scheduler, leaving Recorder untouched."""
    manager: LessRecordsManager | None = hass.data.get(DOMAIN, {}).pop(
        entry.entry_id, None
    )
    if manager is not None:
        manager.async_stop()
    if not hass.data.get(DOMAIN):
        hass.data.pop(DOMAIN, None)
    return True

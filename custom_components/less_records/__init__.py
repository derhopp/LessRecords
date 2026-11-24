"""LessRecords: guarded label-specific Recorder retention."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_APPROVED_FINGERPRINT,
    CONF_DRY_RUN,
    CONF_LABEL_BOUNDARIES,
    CONF_LABEL_SIMULATIONS,
    CONF_POLICIES,
    DOMAIN,
    PLATFORMS,
)
from .manager import LessRecordsManager, get_settings, normalize_run_time
from .migration import async_migrate_legacy_entity_ids
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

    # Migration must be fail-safe. An existing global live approval is NEVER
    # silently inherited by the new per-label switches.
    if CONF_LABEL_SIMULATIONS not in settings:
        settings = {
            **settings,
            CONF_LABEL_SIMULATIONS: {
                label_id: True for label_id in settings[CONF_POLICIES]
            },
            CONF_LABEL_BOUNDARIES: {
                label_id: False for label_id in settings[CONF_POLICIES]
            },
            CONF_DRY_RUN: True,
            CONF_APPROVED_FINGERPRINT: "",
        }
        hass.config_entries.async_update_entry(entry, options=settings)

    # Existing HA entity IDs remain in the entity registry across upgrades.
    # Rename only uncustomized label-only IDs before platforms are loaded.
    # Custom user names/IDs and integration unique IDs are never changed.
    async_migrate_legacy_entity_ids(hass, entry)

    manager = LessRecordsManager(hass, entry)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = manager
    await manager.async_load()
    manager.async_start()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
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
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unloaded:
        return False
    if not hass.data.get(DOMAIN):
        hass.data.pop(DOMAIN, None)
    return True

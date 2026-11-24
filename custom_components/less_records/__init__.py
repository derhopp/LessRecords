"""LessRecords: guarded label-specific Recorder retention."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import (
    CONF_LABEL_BOUNDARIES,
    CONF_LABEL_SIMULATIONS,
    CONF_POLICIES,
    DOMAIN,
    PLATFORMS,
)
from .manager import LessRecordsManager, get_settings, normalize_run_time
from .settings import reset_approval, stable_id
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

    # Preserve every existing device mode; new/legacy entries default to simulation.
    modes = dict(settings.get(CONF_LABEL_SIMULATIONS, {}))
    missing = set(settings[CONF_POLICIES]) - set(modes)
    if missing:
        modes.update(dict.fromkeys(missing, True))
        settings = {
            **settings,
            CONF_LABEL_SIMULATIONS: modes,
            CONF_LABEL_BOUNDARIES: {
                **dict.fromkeys(settings[CONF_POLICIES], False),
                **settings.get(CONF_LABEL_BOUNDARIES, {}),
            },
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


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: ConfigEntry, device_entry: dr.AnyDeviceEntry
) -> bool:
    """Remove the label policy through the purge device's context menu.

    Home Assistant deletes the device registry entry after this returns True.
    Removing a policy never deletes any Recorder history.
    """
    if device_entry.config_entry_id != entry.entry_id:
        return False

    settings = get_settings(entry)
    try:
        policies = validate_policies(settings[CONF_POLICIES])
    except (KeyError, PolicyError, TypeError):
        return False
    if len(policies) <= 1:
        return False

    matching = [
        label_id
        for label_id in policies
        if (DOMAIN, f"{entry.entry_id}_{stable_id(settings, label_id)}")
        in device_entry.identifiers
    ]
    if len(matching) != 1:
        # Never remove the integration hub or another integration's device.
        return False

    label_id = matching[0]
    remaining = {key: days for key, days in policies.items() if key != label_id}
    new_settings = {
        **settings,
        CONF_POLICIES: remaining,
        CONF_LABEL_BOUNDARIES: {
            key: value
            for key, value in settings.get(CONF_LABEL_BOUNDARIES, {}).items()
            if key in remaining
        },
        "policy_ids": {
            key: value
            for key, value in settings.get("policy_ids", {}).items()
            if key in remaining
        },
    }
    reset_approval(new_settings)

    manager = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if manager is not None:
        try:
            await manager._audit("purge_device_removed", label_id=label_id)
        except OSError:
            _LOGGER.warning("Unable to audit removal of label %s", label_id)
        manager.status.pop(label_id, None)
        await manager._persist()

    hass.config_entries.async_update_entry(entry, options=new_settings)
    return True

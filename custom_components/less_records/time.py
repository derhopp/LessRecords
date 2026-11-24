"""One editable global daily purge time on the LessRecords integration hub."""

from __future__ import annotations

from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.const import EntityCategory
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo

from .const import CONF_RUN_TIME, DEFAULT_RUN_TIME, DOMAIN
from .manager import get_settings, normalize_run_time


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Create exactly one common time control for all purge devices."""
    async_add_entities([GlobalPurgeTime(entry)])


class GlobalPurgeTime(TimeEntity):
    """Edit the one integration-wide scheduled purge time."""

    _attr_has_entity_name = True
    _attr_translation_key = "daily_purge_time"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:clock-edit-outline"

    def __init__(self, entry) -> None:
        self.entry = entry
        self._attr_unique_id = f"{entry.entry_id}_daily_purge_time"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_integration")},
            name="LessRecords",
            manufacturer="LessRecords",
            model="Recorder retention controller",
        )

    @property
    def native_value(self) -> time:
        """Return the current shared Home Assistant-local time."""
        return time.fromisoformat(
            normalize_run_time(
                get_settings(self.entry).get(CONF_RUN_TIME, DEFAULT_RUN_TIME)
            )
        )

    async def async_set_value(self, value: time) -> None:
        """Apply a local time to all purge devices on entry reload."""
        if not isinstance(value, time) or value.tzinfo is not None:
            raise HomeAssistantError("A local time without timezone offset is required")
        settings = get_settings(self.entry)
        new_time = normalize_run_time(value.replace(microsecond=0).isoformat())
        if settings.get(CONF_RUN_TIME, DEFAULT_RUN_TIME) == new_time:
            return
        self.hass.config_entries.async_update_entry(
            self.entry,
            options={**settings, CONF_RUN_TIME: new_time},
        )

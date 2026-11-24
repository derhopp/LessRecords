"""Editable label retention in whole days from a purge device."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode

from .const import CONF_POLICIES, MAX_KEEP_DAYS
from .entity import LabelPolicyEntity
from .manager import get_settings
from .settings import async_update_policy


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    manager = hass.data["less_records"][entry.entry_id]
    async_add_entities(
        [RetentionDays(manager, label) for label in get_settings(entry)[CONF_POLICIES]]
    )


class RetentionDays(LabelPolicyEntity, NumberEntity):
    """Modify a single policy without entering the others again."""

    _attr_native_min_value = 1
    _attr_native_max_value = MAX_KEEP_DAYS
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, manager, label_id: str) -> None:
        super().__init__(manager, label_id, "retention_days", "Retention days")

    @property
    def native_value(self) -> float:
        return get_settings(self.entry)[CONF_POLICIES][self.label_id]

    async def async_set_native_value(self, value: float) -> None:
        if not float(value).is_integer():
            raise ValueError("Retention days must be a whole number")
        await async_update_policy(
            self.hass, self.entry, self.label_id, days=int(value)
        )

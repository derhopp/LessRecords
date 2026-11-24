"""Editable target-label picker on each LessRecords purge device."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import label_registry as lr

from .const import CONF_POLICIES
from .entity import LabelPolicyEntity
from .manager import get_settings
from .settings import async_update_policy


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    manager = hass.data["less_records"][entry.entry_id]
    async_add_entities(
        [TargetLabel(manager, label) for label in get_settings(entry)[CONF_POLICIES]]
    )


class TargetLabel(LabelPolicyEntity, SelectEntity):
    """Choose a different existing HA label for this purge policy."""

    _attr_icon = "mdi:label-multiple"

    def __init__(self, manager, label_id: str) -> None:
        super().__init__(manager, label_id, "target_label", "Target label")

    def _options_by_id(self) -> dict[str, str]:
        """Include label IDs to distinguish duplicate friendly names."""
        return {
            label_id: f"{value.name} [{label_id}]"
            for label_id, value in sorted(lr.async_get(self.hass).labels.items())
        }

    @property
    def options(self) -> list[str]:
        return list(self._options_by_id().values())

    @property
    def current_option(self) -> str | None:
        return self._options_by_id().get(self.label_id)

    async def async_select_option(self, option: str) -> None:
        mapping = self._options_by_id()
        label_id = next((key for key, value in mapping.items() if value == option), None)
        if label_id is None:
            raise HomeAssistantError("Unknown target label")
        await async_update_policy(
            self.hass, self.entry, self.label_id, new_label_id=label_id
        )

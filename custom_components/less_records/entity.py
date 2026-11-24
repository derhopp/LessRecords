"""Shared device identity and policy entity helpers."""

from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers import label_registry as lr

from .const import DOMAIN
from .manager import get_settings
from .settings import stable_id


def policy_label_name(hass, label_id: str) -> str:
    """Return friendly HA label name or a stable fallback."""
    item = lr.async_get(hass).labels.get(label_id)
    return item.name if item is not None else label_id


def device_info_for(hass, entry, label_id: str) -> DeviceInfo:
    """One standalone virtual purge device per configured label."""
    settings = get_settings(entry)
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_{stable_id(settings, label_id)}")},
        name=policy_label_name(hass, label_id),
        manufacturer="LessRecords",
        model="Label retention policy",
        configuration_url="https://github.com/derhopp/LessRecords",
    )


class LabelPolicyEntity(Entity):
    """Common identity, device mapping and refresh for a single label policy."""

    _attr_has_entity_name = True

    def __init__(self, manager, label_id: str, key: str, name: str) -> None:
        self.manager = manager
        self.entry = manager.entry
        self.label_id = label_id
        self._attr_name = None
        self._attr_translation_key = key
        self._attr_unique_id = (
            f"{self.entry.entry_id}_{stable_id(get_settings(self.entry), label_id)}_{key}"
        )
        self._attr_device_info = device_info_for(manager.hass, self.entry, label_id)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self.manager.signal, self._handle_manager_update
            )
        )

    @callback
    def _handle_manager_update(self) -> None:
        self.async_write_ha_state()

"""Per-purge-device simulation and retention-boundary switches."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.helpers.entity import DeviceInfo

from .const import CONF_AUDIT_LOG, CONF_POLICIES, DEFAULT_AUDIT_LOG, DOMAIN
from .entity import LabelPolicyEntity
from .manager import get_settings
from .settings import (
    async_set_simulation,
    async_update_policy,
    boundary_enabled,
    is_simulation,
)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    manager = hass.data["less_records"][entry.entry_id]
    entities = []
    for label in get_settings(entry)[CONF_POLICIES]:
        entities.extend((SimulationSwitch(manager, label), BoundarySwitch(manager, label)))
    entities.append(AuditLogSwitch(entry))
    async_add_entities(entities)


class SimulationSwitch(LabelPolicyEntity, SwitchEntity):
    """On = dry run, Off = real deletion, subject to live approval."""

    _attr_icon = "mdi:flask-outline"

    def __init__(self, manager, label_id: str) -> None:
        super().__init__(manager, label_id, "simulation", "Simulation mode")

    @property
    def is_on(self) -> bool:
        return is_simulation(get_settings(self.entry), self.label_id)

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Concise warning shown in the switch's More info details."""
        german = self.hass.config.language.startswith("de")
        return {
            "warning": (
                "Aus: Löschen erst nach Gerätefreigabe. Backup prüfen."
                if german
                else "OFF: approve on this device first. Verify backup."
            )
        }

    async def async_turn_on(self, **kwargs) -> None:
        await async_set_simulation(self.hass, self.entry, self.label_id, True)

    async def async_turn_off(self, **kwargs) -> None:
        await async_set_simulation(self.hass, self.entry, self.label_id, False)


class BoundarySwitch(LabelPolicyEntity, SwitchEntity):
    """Opt into experimental historical anchor-state preservation.

    Changing this option always revokes all live approvals, so a warning and
    separate scope confirmation is required before any real Recorder writes.
    """

    _attr_icon = "mdi:chart-timeline-variant"

    def __init__(self, manager, label_id: str) -> None:
        super().__init__(manager, label_id, "preserve_boundary", "Preserve boundary state")

    @property
    def is_on(self) -> bool:
        return boundary_enabled(get_settings(self.entry), self.label_id)

    async def async_turn_on(self, **kwargs) -> None:
        await async_update_policy(self.hass, self.entry, self.label_id, boundary=True)

    async def async_turn_off(self, **kwargs) -> None:
        await async_update_policy(self.hass, self.entry, self.label_id, boundary=False)


class AuditLogSwitch(SwitchEntity):
    """Edit the global audit setting directly on the integration hub."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:file-document-edit-outline"
    _attr_translation_key = "audit_log_enabled"

    def __init__(self, entry) -> None:
        self.entry = entry
        self.entity_description = SwitchEntityDescription(
            key="audit_log_enabled",
            name="Audit logging",
            translation_key="audit_log_enabled",
            has_entity_name=True,
            entity_registry_enabled_default=True,
        )
        self._attr_unique_id = f"{entry.entry_id}_audit_log_enabled"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_integration")},
            name="LessRecords",
            manufacturer="LessRecords",
            model="Recorder retention controller",
        )

    @property
    def is_on(self) -> bool:
        return bool(get_settings(self.entry).get(CONF_AUDIT_LOG, DEFAULT_AUDIT_LOG))

    async def async_turn_on(self, **kwargs) -> None:
        await self._set_enabled(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._set_enabled(False)

    async def _set_enabled(self, value: bool) -> None:
        settings = get_settings(self.entry)
        if settings.get(CONF_AUDIT_LOG, DEFAULT_AUDIT_LOG) is value:
            return
        self.hass.config_entries.async_update_entry(
            self.entry,
            options={**settings, CONF_AUDIT_LOG: value},
        )

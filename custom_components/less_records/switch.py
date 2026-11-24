"""Per-purge-device simulation and retention-boundary switches."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity

from .const import CONF_POLICIES
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
                "Aus: Löschen erst nach Freigabe. Vorher Backup prüfen."
                if german
                else "OFF: deletion requires approval. Verify your backup."
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

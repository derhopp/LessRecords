"""Purge-device telemetry and a visible integration audit-log sensor."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.util import dt as dt_util

from .const import (
    CONF_POLICIES,
    CONF_RUN_TIME,
    DEFAULT_RUN_TIME,
    DOMAIN,
)
from .entity import LabelPolicyEntity
from .manager import get_settings, targets_for_policy
from .settings import is_simulation

SCAN_INTERVAL = timedelta(minutes=1)

SENSORS = {
    "matching_devices": "Matching devices",
    "last_purge_run": "Last purge run",
    "last_run": "Last run",
    "next_purge_run": "Next purge run",
}


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    manager = hass.data[DOMAIN][entry.entry_id]
    items = [
        PurgePolicySensor(manager, label, key, name)
        for label in get_settings(entry)[CONF_POLICIES]
        for key, name in SENSORS.items()
    ]
    items.append(AuditLogSensor(manager))
    async_add_entities(items)


class PurgePolicySensor(LabelPolicyEntity, SensorEntity):
    """Expose label coverage and retained run timestamps."""

    _attr_should_poll = True

    def __init__(self, manager, label_id: str, key: str, name: str) -> None:
        super().__init__(manager, label_id, key, name)
        self.key = key
        if key.endswith("_run"):
            self._attr_device_class = SensorDeviceClass.TIMESTAMP
        if key == "matching_devices":
            self._attr_icon = "mdi:devices"

    @property
    def native_value(self) -> Any:
        if self.key == "matching_devices":
            _, devices = targets_for_policy(self.hass, self.label_id)
            return len(devices)
        if self.key == "next_purge_run":
            # The next evaluation is meaningful even when a device simulates.
            now = dt_util.now()
            clock = datetime.strptime(
                get_settings(self.entry).get(CONF_RUN_TIME, DEFAULT_RUN_TIME),
                "%H:%M:%S",
            ).time()
            next_time = datetime.combine(now.date(), clock, tzinfo=now.tzinfo)
            if next_time <= now:
                next_time += timedelta(days=1)
            return next_time
        recorded = self.manager.status.get(self.label_id, {}).get(self.key)
        return datetime.fromisoformat(recorded) if recorded else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.key == "matching_devices":
            entities, devices = targets_for_policy(self.hass, self.label_id)
            return {"matching_entities": len(entities)}
        if self.key == "last_purge_run":
            return {
                "note": "Last submitted purge request, not verified deletion",
                "has_submitted_purge": bool(
                    self.manager.status.get(self.label_id, {}).get("last_purge_run")
                ),
            }
        if self.key == "last_run":
            return {"note": "Latest simulation or live attempt"}
        if self.key == "next_purge_run":
            return {
                "run_mode": (
                    "simulation"
                    if is_simulation(get_settings(self.entry), self.label_id)
                    else "live"
                ),
                "note": "Next scheduled evaluation, including simulation runs",
            }
        return None


class AuditLogSensor(SensorEntity):
    """Last audit event on the LessRecords integration hub device."""

    _attr_has_entity_name = True
    _attr_translation_key = "audit_log"
    _attr_icon = "mdi:text-box-search-outline"
    _attr_should_poll = False

    def __init__(self, manager) -> None:
        self.manager = manager
        self._attr_unique_id = f"{manager.entry.entry_id}_audit"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{manager.entry.entry_id}_integration")},
            name="LessRecords",
            manufacturer="LessRecords",
            model="Recorder retention controller",
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        from homeassistant.helpers.dispatcher import async_dispatcher_connect

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self.manager.signal, self.async_write_ha_state
            )
        )

    @property
    def native_value(self) -> str:
        return str(self.manager.last_audit.get("action") or "No activity yet")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "last_event": self.manager.last_audit,
            "full_log": "Open integration Diagnostics to download the latest audit excerpt",
            "file": "less_records_audit.log (within Home Assistant /config)",
        }

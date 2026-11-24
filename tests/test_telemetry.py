"""Purge device telemetry must be visible and consistent in all run modes."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.less_records.manager import LessRecordsManager
from custom_components.less_records.sensor import PurgePolicySensor


def make_sensor(key: str, *, simulation: bool = True):
    entry = SimpleNamespace(
        entry_id="entry-1",
        data={
            "policies": {"short": 30},
            "label_simulations": {"short": simulation},
            "run_time": "12:34:00",
            "audit_log": True,
            "dry_run": simulation,
            "approved_fingerprint": "" if simulation else "approved",
        },
        options={},
    )
    hass = MagicMock()
    hass.config = SimpleNamespace(time_zone="Europe/Berlin")
    manager = SimpleNamespace(
        entry=entry,
        hass=hass,
        status={"short": {}},
        signal="less_records_test",
    )
    with patch(
        "custom_components.less_records.entity.lr.async_get",
        return_value=SimpleNamespace(
            labels={"short": SimpleNamespace(name="Short")}
        ),
    ):
        item = PurgePolicySensor(manager, "short", key, key.replace("_", " ").title())
    return item, manager


@pytest.mark.parametrize("key", ["last_run", "last_purge_run", "next_purge_run"])
def test_each_timestamp_sensor_declares_timestamp_device_class(key):
    sensor, _ = make_sensor(key)
    from homeassistant.components.sensor import SensorDeviceClass

    assert sensor.device_class == SensorDeviceClass.TIMESTAMP
    assert sensor.unique_id.endswith(f"_{key}")
    assert sensor.entity_description.name != ""
    assert sensor.entity_description.translation_key == key
    assert sensor.entity_description.entity_registry_enabled_default is True
    assert sensor.entity_description.entity_registry_visible_default is True
    assert sensor.state_class is None
    assert sensor.native_unit_of_measurement is None
    assert sensor.options is None
    assert sensor.suggested_display_precision is None


@pytest.mark.parametrize("simulation", [True, False])
def test_next_run_is_visible_in_simulation_and_live_mode(simulation):
    sensor, _ = make_sensor("next_purge_run", simulation=simulation)
    # Force deterministic local time. The scheduled run is always in the future.
    now = datetime(2026, 11, 24, 11, 15, tzinfo=timezone.utc)
    with patch("custom_components.less_records.sensor.dt_util.now", return_value=now):
        value = sensor.native_value
    assert isinstance(value, datetime)
    assert value > now
    assert sensor.extra_state_attributes["run_mode"] == (
        "simulation" if simulation else "live"
    )


def test_last_run_and_purge_request_remain_distinct():
    last, manager = make_sensor("last_run")
    purge, _ = make_sensor("last_purge_run")
    purge.manager = manager
    manager.status["short"]["last_run"] = "2026-11-24T10:00:00+00:00"
    assert last.native_value == datetime(2026, 11, 24, 10, tzinfo=timezone.utc)
    assert purge.native_value is None
    manager.status["short"]["last_purge_run"] = "2026-11-24T10:05:00+00:00"
    assert purge.native_value == datetime(
        2026, 11, 24, 10, 5, tzinfo=timezone.utc
    )


@pytest.mark.asyncio
async def test_blocked_recorder_run_still_updates_last_run_and_persists_it():
    entry = SimpleNamespace(
        entry_id="entry-1",
        data={
            "policies": {"short": 30},
            "run_time": "12:34:00",
            "label_simulations": {"short": True},
            "dry_run": True,
            "audit_log": True,
        },
        options={},
    )
    hass = MagicMock()
    with patch("custom_components.less_records.manager.Store"):
        manager = LessRecordsManager(hass, entry)
    manager._audit = AsyncMock()
    manager._persist = AsyncMock()
    from custom_components.less_records.policy import PolicyError

    with patch(
        "custom_components.less_records.manager.preflight",
        side_effect=PolicyError("recorder unavailable"),
    ):
        await manager.async_run()
    assert manager.status["short"]["last_run"] is not None
    manager._persist.assert_awaited_once()
    hass.services.async_call.assert_not_called()

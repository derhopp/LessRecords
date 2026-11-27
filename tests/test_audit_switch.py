"""The integration hub exposes audit settings without a gear menu."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from custom_components.less_records.switch import AuditLogSwitch


@pytest.mark.asyncio
async def test_audit_switch_is_on_by_default_and_changes_only_audit_setting():
    entry = SimpleNamespace(
        entry_id="test-entry",
        data={"policies": {"heat": 7}, "run_time": "06:30:00"},
        options={},
    )
    sensor = AuditLogSwitch(entry)
    sensor.hass = MagicMock()
    assert sensor.is_on is True

    await sensor.async_turn_off()
    update = sensor.hass.config_entries.async_update_entry.call_args.kwargs
    assert update["options"]["audit_log"] is False
    assert update["options"]["policies"] == {"heat": 7}
    assert sensor.unique_id.endswith("_audit_log_enabled")

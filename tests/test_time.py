"""Integration-wide scheduling control: a single time entity for all labels."""

from datetime import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from custom_components.less_records.time import GlobalPurgeTime
from homeassistant.exceptions import HomeAssistantError


@pytest.mark.asyncio
async def test_time_entity_updates_only_the_shared_daily_time():
    entry = SimpleNamespace(
        entry_id="abc",
        data={"run_time": "06:30:00", "policies": {"heat": 7}},
        options={},
    )
    entity = GlobalPurgeTime(entry)
    entity.hass = MagicMock()
    assert entity.native_value == time(6, 30)
    await entity.async_set_value(time(9, 15))
    result = entity.hass.config_entries.async_update_entry.call_args.kwargs["options"]
    assert result["run_time"] == "09:15:00"
    assert result["policies"] == {"heat": 7}


@pytest.mark.asyncio
async def test_time_rejects_offset_times():
    entry = SimpleNamespace(entry_id="abc", data={}, options={})
    entity = GlobalPurgeTime(entry)
    entity.hass = MagicMock()
    with pytest.raises(HomeAssistantError):
        await entity.async_set_value("09:15")

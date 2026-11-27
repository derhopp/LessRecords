"""The integration gear is exclusively an add-purge-device wizard."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from custom_components.less_records.config_flow import LessRecordsOptionsFlow


@pytest.fixture
def editor(hass):
    entry = SimpleNamespace(
        data={
            "policies": {"heat": 7, "power": 90},
            "run_time": "06:30:00",
            "audit_log": True,
            "label_simulations": {"heat": False, "power": True},
            "label_boundaries": {"heat": False, "power": False},
            "label_approvals": {"heat": "old-approval"},
            "approved_fingerprint": "old-approval",
        },
        options={},
    )
    flow = LessRecordsOptionsFlow(entry)
    flow.hass = hass
    registry = SimpleNamespace(
        labels={
            "heat": SimpleNamespace(name="Heating"),
            "power": SimpleNamespace(name="Energy"),
            "added": SimpleNamespace(name="Added"),
        }
    )
    with patch(
        "custom_components.less_records.config_flow.lr.async_get",
        return_value=registry,
    ):
        yield flow, entry


@pytest.mark.asyncio
async def test_gear_opens_add_form_directly_without_redundant_menu(editor):
    flow, _ = editor
    form = await flow.async_step_init()
    assert form["type"] == "form"
    assert form["step_id"] == "init"
    assert {key.schema for key in form["data_schema"].schema} == {
        "label", "keep_days"
    }
    assert not hasattr(flow, "async_step_settings")
    assert not hasattr(flow, "async_step_activate")
    assert not hasattr(flow, "async_step_remove_policy")


@pytest.mark.asyncio
async def test_add_only_keeps_existing_modes_and_defaults_new_device_to_simulation(editor):
    flow, entry = editor
    step = await flow.async_step_init({"label": "added", "keep_days": 14})
    assert step["step_id"] == "confirm"
    assert step["description_placeholders"] == {
        "label": "Added", "days": "14"
    }
    result = await flow.async_step_confirm({"acknowledge": True})
    assert result["type"] == "create_entry"
    cfg = result["data"]
    assert cfg["policies"] == {"heat": 7, "power": 90, "added": 14}
    assert cfg["label_simulations"] == {
        "heat": False, "power": True, "added": True
    }
    assert cfg["label_boundaries"]["added"] is False
    assert cfg["label_approvals"] == {}
    assert cfg["approved_fingerprint"] == ""
    assert cfg["run_time"] == entry.data["run_time"]
    assert cfg["audit_log"] is True


@pytest.mark.asyncio
async def test_cannot_add_duplicate_label(editor):
    flow, _ = editor
    step = await flow.async_step_init({"label": "heat", "keep_days": 20})
    assert step["type"] == "form"
    assert step["errors"]["label"] == "duplicate_label"


@pytest.mark.asyncio
async def test_cannot_add_unknown_label(editor):
    flow, _ = editor
    step = await flow.async_step_init({"label": "missing", "keep_days": 20})
    assert step["errors"]["label"] == "unknown_label"


@pytest.mark.asyncio
async def test_invalid_retention_is_rejected(editor):
    flow, _ = editor
    step = await flow.async_step_init({"label": "added", "keep_days": 1.5})
    assert step["errors"]["keep_days"] == "invalid_retention"


@pytest.mark.asyncio
async def test_confirmation_must_be_explicit(editor):
    flow, _ = editor
    await flow.async_step_init({"label": "added", "keep_days": 20})
    result = await flow.async_step_confirm({"acknowledge": False})
    assert result["type"] == "form"
    assert result["errors"]["base"] == "acknowledgement_required"


@pytest.mark.asyncio
async def test_changed_existing_policy_blocks_stale_add(editor):
    flow, entry = editor
    await flow.async_step_init({"label": "added", "keep_days": 14})
    entry.options = {"policies": {"heat": 14, "power": 90}}
    result = await flow.async_step_confirm({"acknowledge": True})
    assert result["type"] == "abort"
    assert result["reason"] == "policies_changed"

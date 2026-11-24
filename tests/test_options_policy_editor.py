"""Regression tests for editing existing label retention policies via OptionsFlow."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from custom_components.less_records.config_flow import LessRecordsOptionsFlow

BASE = {
    "policies": {"heat": 7, "power": 90},
    "run_time": "06:30:00",
    "audit_log": True,
    "dry_run": False,
    "approved_fingerprint": "previous-approval",
}


@pytest.fixture
def editor(hass):
    """Provide a real OptionsFlow with isolated registry and entry settings."""
    entry = SimpleNamespace(data=dict(BASE), options={})
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
async def test_choose_existing_policy_shows_saved_days(editor):
    flow, _ = editor
    menu = await flow.async_step_policies()
    assert menu["type"] == "menu"
    assert "edit_policy" in menu["menu_options"]
    selection = await flow.async_step_edit_policy({"label": "power"})
    assert selection["type"] == "form"
    form = await flow.async_step_edit_retention()
    assert form["type"] == "form"
    assert form["description_placeholders"]["current_days"] == "90"
    # The existing saved value is the actual form default (not a blank input).
    marker = next(
        key for key in form["data_schema"].schema if key.schema == "keep_days"
    )
    assert marker.default() == 90


@pytest.mark.asyncio
async def test_edit_updates_only_selected_policy_and_revokes_approval(editor):
    flow, entry = editor
    await flow.async_step_policies()
    await flow.async_step_edit_policy({"label": "power"})
    await flow.async_step_edit_retention({"keep_days": 30})
    assert flow._pending_policies == {"heat": 7, "power": 30}
    assert entry.data["policies"] == {"heat": 7, "power": 90}
    result = await flow.async_step_policy_warning({"acknowledge": True})
    assert result["type"] == "create_entry"
    assert result["data"]["policies"] == {"heat": 7, "power": 30}
    assert result["data"]["run_time"] == BASE["run_time"]
    assert result["data"]["dry_run"] is False
    assert result["data"]["approved_fingerprint"] == ""


@pytest.mark.asyncio
async def test_add_keeps_all_existing_policies(editor):
    flow, _ = editor
    await flow.async_step_policies()
    await flow.async_step_add_policy({"label": "added", "keep_days": 14})
    result = await flow.async_step_policy_warning({"acknowledge": True})
    assert result["data"]["policies"] == {
        "heat": 7, "power": 90, "added": 14
    }


@pytest.mark.asyncio
async def test_remove_keeps_other_policies(editor):
    flow, _ = editor
    await flow.async_step_policies()
    await flow.async_step_remove_policy({"label": "heat"})
    result = await flow.async_step_policy_warning({"acknowledge": True})
    assert result["data"]["policies"] == {"power": 90}
    assert result["data"]["dry_run"] is True


@pytest.mark.asyncio
async def test_refuses_removal_of_last_policy(editor):
    flow, entry = editor
    entry.options = {"policies": {"heat": 7}}
    await flow.async_step_policies()
    result = await flow.async_step_remove_policy()
    assert result["type"] == "abort"
    assert result["reason"] == "last_policy_required"


@pytest.mark.asyncio
async def test_refuses_stale_policy_edit(editor):
    flow, entry = editor
    await flow.async_step_policies()
    await flow.async_step_edit_policy({"label": "heat"})
    await flow.async_step_edit_retention({"keep_days": 10})
    entry.options = {"policies": {"heat": 7, "power": 60}}
    result = await flow.async_step_policy_warning({"acknowledge": True})
    assert result["type"] == "abort"
    assert result["reason"] == "policies_changed"


@pytest.mark.asyncio
async def test_refuses_unconfirmed_policy_change(editor):
    flow, _ = editor
    await flow.async_step_policies()
    await flow.async_step_edit_policy({"label": "heat"})
    await flow.async_step_edit_retention({"keep_days": 10})
    result = await flow.async_step_policy_warning({"acknowledge": False})
    assert result["type"] == "form"
    assert result["errors"]["base"] == "acknowledgement_required"


@pytest.mark.asyncio
async def test_unchanged_retention_preserves_live_approval(editor):
    flow, _ = editor
    await flow.async_step_policies()
    await flow.async_step_edit_policy({"label": "heat"})
    result = await flow.async_step_edit_retention({"keep_days": 7})
    assert result["type"] == "create_entry"
    assert result["data"]["dry_run"] is False
    assert result["data"]["approved_fingerprint"] == "previous-approval"

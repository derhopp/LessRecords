"""Approval is per purge device with a visible, time-limited warning."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.less_records.button import ApprovePurgeButton
from custom_components.less_records.policy import PolicyError, PurgePlan
from homeassistant.exceptions import HomeAssistantError


def setup_button():
    entry = SimpleNamespace(
        entry_id="test-entry",
        data={
            "policies": {"heat": 7, "power": 90},
            "label_simulations": {"heat": False, "power": True},
            "label_boundaries": {"heat": False, "power": False},
            "label_approvals": {},
        },
        options={},
    )
    hass = MagicMock()
    hass.config.language = "en"
    manager = SimpleNamespace(
        entry=entry,
        hass=hass,
        approval_lock=asyncio.Lock(),
        pending_approvals={},
        _audit=AsyncMock(),
    )
    with patch(
        "custom_components.less_records.entity.lr.async_get",
        return_value=SimpleNamespace(
            labels={"heat": SimpleNamespace(name="Heating")}
        ),
    ):
        button = ApprovePurgeButton(manager, "heat")
    button.hass = hass
    button._context = SimpleNamespace(user_id="admin-user")
    hass.auth.async_get_user = AsyncMock(return_value=SimpleNamespace(is_admin=True))
    return button, manager, hass


@pytest.mark.asyncio
async def test_first_press_only_shows_warning_and_does_not_approve():
    button, manager, hass = setup_button()
    plan = PurgePlan({7: ("sensor.heat",)}, "reviewed")
    with (
        patch("custom_components.less_records.button.preflight", return_value=plan),
        patch("custom_components.less_records.button.policy_label_name", return_value="Heating"),
        patch("custom_components.less_records.manager.targets_for_policy",
              return_value=({"sensor.heat"}, set())),
        patch("custom_components.less_records.button.persistent_notification.async_create") as note,
    ):
        await button.async_press()

    note.assert_called_once()
    assert "backup" in note.call_args.args[1].lower()
    assert "7 days" in note.call_args.args[1]
    assert manager.pending_approvals["heat"][0].startswith(plan.fingerprint)
    hass.config_entries.async_update_entry.assert_not_called()
    hass.services.async_call.assert_not_called()


@pytest.mark.asyncio
async def test_second_press_approves_only_its_label_without_changing_simulation():
    button, manager, hass = setup_button()
    plan = PurgePlan({7: ("sensor.heat",)}, "reviewed")
    with (
        patch("custom_components.less_records.button.preflight", return_value=plan),
        patch("custom_components.less_records.button.policy_label_name", return_value="Heating"),
        patch("custom_components.less_records.manager.targets_for_policy",
              return_value=({"sensor.heat"}, set())),
        patch("custom_components.less_records.button.persistent_notification.async_create"),
        patch("custom_components.less_records.button.persistent_notification.async_dismiss") as dismissed,
    ):
        await button.async_press()
        await button.async_press()

    opts = hass.config_entries.async_update_entry.call_args.kwargs["options"]
    assert opts["label_approvals"] == {"heat": "reviewed"}
    assert opts["label_simulations"] == {"heat": False, "power": True}
    assert manager.pending_approvals == {}
    manager._audit.assert_awaited_once()
    dismissed.assert_called_once()
    hass.services.async_call.assert_not_called()


@pytest.mark.asyncio
async def test_expired_warning_never_approves():
    button, manager, hass = setup_button()
    manager.pending_approvals["heat"] = ("reviewed:False", -1)
    plan = PurgePlan({7: ("sensor.heat",)}, "reviewed")
    with (
        patch("custom_components.less_records.button.preflight", return_value=plan),
        patch("custom_components.less_records.button.policy_label_name", return_value="Heating"),
        patch("custom_components.less_records.manager.targets_for_policy",
              return_value=({"sensor.heat"}, set())),
        patch("custom_components.less_records.button.persistent_notification.async_create"),
    ):
        await button.async_press()
    hass.config_entries.async_update_entry.assert_not_called()


@pytest.mark.asyncio
async def test_scope_change_blocks_second_press():
    button, manager, hass = setup_button()
    plan = PurgePlan({7: ("sensor.heat",)}, "reviewed")
    changed = PurgePlan({7: ("sensor.heat", "sensor.extra")}, "new-plan")
    with (
        patch("custom_components.less_records.button.preflight",
              side_effect=[plan, changed]),
        patch("custom_components.less_records.button.policy_label_name", return_value="Heating"),
        patch("custom_components.less_records.manager.targets_for_policy",
              return_value=({"sensor.heat"}, set())),
        patch("custom_components.less_records.button.persistent_notification.async_create"),
    ):
        await button.async_press()
        # A changed plan creates a new warning rather than authorizing.
        await button.async_press()
    hass.config_entries.async_update_entry.assert_not_called()
    assert manager.pending_approvals["heat"][0].startswith("new-plan")


@pytest.mark.asyncio
async def test_recorder_not_ready_blocks_approval_and_never_queues_purge():
    button, manager, hass = setup_button()
    with (
        patch("custom_components.less_records.button.preflight",
              side_effect=PolicyError("Recorder unavailable")),
        pytest.raises(HomeAssistantError, match="not safe"),
    ):
        await button.async_press()
    hass.config_entries.async_update_entry.assert_not_called()
    hass.services.async_call.assert_not_called()


@pytest.mark.asyncio
async def test_non_admin_cannot_begin_approval_or_request_purge():
    button, manager, hass = setup_button()
    hass.auth.async_get_user.return_value = SimpleNamespace(is_admin=False)
    with pytest.raises(HomeAssistantError, match="administrator"):
        await button.async_press()
    assert manager.pending_approvals == {}
    hass.config_entries.async_update_entry.assert_not_called()
    hass.services.async_call.assert_not_called()


@pytest.mark.asyncio
async def test_automation_without_authenticated_user_cannot_approve():
    button, manager, hass = setup_button()
    button._context = SimpleNamespace(user_id=None)
    with pytest.raises(HomeAssistantError, match="authenticated"):
        await button.async_press()
    assert manager.pending_approvals == {}
    hass.auth.async_get_user.assert_not_awaited()

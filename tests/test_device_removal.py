"""Regression tests for purge-device context-menu removal.

The integration must remove the policy, not state history; the native Home
Assistant device registry removes the corresponding device after True.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.less_records import async_remove_config_entry_device
from custom_components.less_records.const import DOMAIN


def make_context(*, policies=None, device_id=None, entry_id="test-entry"):
    policies = policies or {"short": 7, "long": 365}
    entry = SimpleNamespace(
        entry_id=entry_id,
        data={
            "policies": policies,
            "label_simulations": dict.fromkeys(policies, False),
            "label_boundaries": dict.fromkeys(policies, True),
            "approved_fingerprint": "previously-approved",
            "dry_run": False,
            "policy_ids": {key: f"label_{key}" for key in policies},
            "run_time": "06:30:00",
        },
        options={},
    )
    selected_id = device_id or "short"
    device = SimpleNamespace(
        config_entry_id=entry_id,
        identifiers={(DOMAIN, f"{entry_id}_label_{selected_id}")},
    )
    manager = SimpleNamespace(
        status={"short": {"last_run": "2026-11-24T07:00:00+00:00"}},
        _audit=AsyncMock(),
        _persist=AsyncMock(),
    )
    hass = MagicMock()
    hass.data = {DOMAIN: {entry_id: manager}}
    return hass, entry, device, manager


@pytest.mark.asyncio
async def test_device_menu_removal_removes_only_selected_policy_and_revokes_approval():
    hass, entry, device, manager = make_context()
    assert await async_remove_config_entry_device(hass, entry, device)
    updated = hass.config_entries.async_update_entry.call_args.kwargs["options"]
    assert updated["policies"] == {"long": 365}
    assert updated["dry_run"] is False
    assert updated["approved_fingerprint"] == ""
    assert updated["label_simulations"] == {"long": False}
    assert updated["label_boundaries"] == {"long": True}
    assert updated["policy_ids"] == {"long": "label_long"}
    manager._audit.assert_awaited_once_with("purge_device_removed", label_id="short")
    manager._persist.assert_awaited_once()
    assert "short" not in manager.status


@pytest.mark.asyncio
async def test_cannot_remove_last_purge_device():
    hass, entry, device, _ = make_context(policies={"short": 7})
    assert not await async_remove_config_entry_device(hass, entry, device)
    hass.config_entries.async_update_entry.assert_not_called()


@pytest.mark.asyncio
async def test_cannot_remove_integration_hub():
    hass, entry, _, _ = make_context()
    hub = SimpleNamespace(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{entry.entry_id}_integration")},
    )
    assert not await async_remove_config_entry_device(hass, entry, hub)
    hass.config_entries.async_update_entry.assert_not_called()


@pytest.mark.asyncio
async def test_cannot_remove_foreign_or_forged_device():
    hass, entry, device, _ = make_context()
    device.config_entry_id = "another-config-entry"
    assert not await async_remove_config_entry_device(hass, entry, device)
    device.config_entry_id = entry.entry_id
    device.identifiers = {(DOMAIN, f"{entry.entry_id}_unrelated")}
    assert not await async_remove_config_entry_device(hass, entry, device)
    hass.config_entries.async_update_entry.assert_not_called()


@pytest.mark.asyncio
async def test_changed_policy_does_not_perform_any_recorder_deletion():
    hass, entry, device, _ = make_context()
    assert await async_remove_config_entry_device(hass, entry, device)
    hass.services.async_call.assert_not_called()

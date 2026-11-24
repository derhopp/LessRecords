"""Policy switches, stable IDs and no-bypass safety tests."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from custom_components.less_records import settings
from homeassistant.exceptions import HomeAssistantError


def create_fixture():
    entry = SimpleNamespace(
        data={
            "policies": {"heat": 7, "important": 365},
            "dry_run": False,
            "approved_fingerprint": "approved",
            "label_simulations": {"heat": True, "important": True},
            "label_boundaries": {"heat": False, "important": False},
            "policy_ids": {"heat": "stable-a", "important": "stable-b"},
        },
        options={},
    )
    hass = MagicMock()
    registry = SimpleNamespace(
        labels={
            "heat": SimpleNamespace(name="Heat"),
            "important": SimpleNamespace(name="Important"),
            "new": SimpleNamespace(name="New"),
        }
    )
    return hass, entry, registry


@pytest.mark.asyncio
async def test_change_retention_only_changes_one_policy_and_resets_all_simulations():
    hass, entry, registry = create_fixture()
    with patch("custom_components.less_records.settings.lr.async_get", return_value=registry):
        await settings.async_update_policy(hass, entry, "heat", days=14)
    changed = hass.config_entries.async_update_entry.call_args.kwargs["options"]
    assert changed["policies"] == {"heat": 14, "important": 365}
    assert changed["label_simulations"] == {"heat": True, "important": True}
    assert changed["dry_run"] is True
    assert changed["approved_fingerprint"] == ""
    assert changed["policy_ids"] == entry.data["policy_ids"]


@pytest.mark.asyncio
async def test_retargeted_label_preserves_virtual_device_id():
    hass, entry, registry = create_fixture()
    with patch("custom_components.less_records.settings.lr.async_get", return_value=registry):
        await settings.async_update_policy(hass, entry, "heat", new_label_id="new")
    changed = hass.config_entries.async_update_entry.call_args.kwargs["options"]
    assert changed["policies"] == {"important": 365, "new": 7}
    assert changed["policy_ids"]["new"] == "stable-a"
    assert "heat" not in changed["policy_ids"]


@pytest.mark.asyncio
async def test_cannot_retarget_to_already_configured_label():
    hass, entry, registry = create_fixture()
    with (
        patch("custom_components.less_records.settings.lr.async_get", return_value=registry),
        pytest.raises(HomeAssistantError, match="already"),
    ):
        await settings.async_update_policy(hass, entry, "heat", new_label_id="important")
    hass.config_entries.async_update_entry.assert_not_called()


@pytest.mark.asyncio
async def test_boundary_opt_in_forces_new_approval():
    hass, entry, registry = create_fixture()
    with patch("custom_components.less_records.settings.lr.async_get", return_value=registry):
        await settings.async_update_policy(hass, entry, "heat", boundary=True)
    changed = hass.config_entries.async_update_entry.call_args.kwargs["options"]
    assert changed["label_boundaries"]["heat"] is True
    assert changed["dry_run"] is True
    assert changed["approved_fingerprint"] == ""


@pytest.mark.asyncio
async def test_can_never_disable_simulation_without_approval():
    hass, entry, registry = create_fixture()
    entry.options = {"dry_run": True, "approved_fingerprint": ""}
    with pytest.raises(HomeAssistantError, match="not approved"):
        await settings.async_set_simulation(hass, entry, "heat", False)
    hass.config_entries.async_update_entry.assert_not_called()


@pytest.mark.asyncio
async def test_can_disable_only_one_switch_after_valid_scope_approval():
    hass, entry, registry = create_fixture()
    plan = SimpleNamespace(fingerprint="approved")
    with patch("custom_components.less_records.settings.current_plan", return_value=plan):
        await settings.async_set_simulation(hass, entry, "heat", False)
    changed = hass.config_entries.async_update_entry.call_args.kwargs["options"]
    assert changed["label_simulations"] == {"heat": False, "important": True}
    assert changed["approved_fingerprint"] == "approved"


def test_missing_simulation_mapping_defaults_safe():
    assert settings.is_simulation({"dry_run": False}, "heat") is True

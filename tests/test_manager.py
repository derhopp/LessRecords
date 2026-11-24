"""Verify Recorder requests are explicit and can never occur in dry-run."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.less_records.manager import (
    LessRecordsManager,
    normalize_run_time,
)
from custom_components.less_records.policy import PolicyError, PurgePlan
from custom_components.less_records.recorder_guard import check_approval


def make_entry(dry_run: bool, signature: str = "") -> SimpleNamespace:
    return SimpleNamespace(
        entry_id="test-entry",
        data={
            "policies": {"a": 7},
            "run_time": "06:30:00",
            "audit_log": True,
            "dry_run": dry_run,
            "approved_fingerprint": signature,
            "label_simulations": {"a": dry_run},
            "label_boundaries": {"a": False},
        },
        options={},
    )


def make_manager(dry_run: bool, signature: str = "") -> tuple:
    hass = SimpleNamespace(
        services=SimpleNamespace(async_call=AsyncMock()),
        config=SimpleNamespace(path=lambda filename: filename),
        async_add_executor_job=AsyncMock(),
    )
    with patch("custom_components.less_records.manager.Store"):
        manager = LessRecordsManager(hass, make_entry(dry_run, signature))
    manager._audit = AsyncMock()
    manager._persist = AsyncMock()
    manager._matching_label_ids = MagicMock(return_value={"a"})
    return manager, hass


PLAN = PurgePlan({7: ("sensor.one", "sensor.two")}, "approved-hash")
CHANGED = PurgePlan({7: ("sensor.one", "sensor.two", "sensor.three")}, "new-hash")


@pytest.mark.asyncio
async def test_simulation_never_calls_recorder() -> None:
    manager, hass = make_manager(True)
    with patch(
        "custom_components.less_records.manager.preflight", return_value=PLAN
    ):
        await manager.async_run()

    hass.services.async_call.assert_not_awaited()
    assert any(
        call.args[0] == "simulated"
        for call in manager._audit.await_args_list
    )


@pytest.mark.asyncio
async def test_unapproved_live_run_never_calls_recorder() -> None:
    manager, hass = make_manager(False)
    with patch(
        "custom_components.less_records.manager.preflight", return_value=PLAN
    ):
        await manager.async_run()
    hass.services.async_call.assert_not_awaited()


@pytest.mark.asyncio
async def test_live_request_only_uses_explicit_ids_and_retention() -> None:
    manager, hass = make_manager(False, PLAN.fingerprint)
    with patch(
        "custom_components.less_records.manager.preflight", return_value=PLAN
    ):
        await manager.async_run()
    hass.services.async_call.assert_awaited_once_with(
        "recorder",
        "purge_entities",
        {"entity_id": ["sensor.one", "sensor.two"], "keep_days": 7},
        blocking=True,
    )
    assert any(
        call.args[0] == "request_pending"
        for call in manager._audit.await_args_list
    )
    assert any(
        call.args[0] == "request_submitted"
        for call in manager._audit.await_args_list
    )


@pytest.mark.asyncio
async def test_audit_failure_blocks_destructive_request() -> None:
    manager, hass = make_manager(False, PLAN.fingerprint)
    manager._audit.side_effect = OSError("audit file unwritable")
    with patch(
        "custom_components.less_records.manager.preflight", return_value=PLAN
    ):
        await manager.async_run()
    hass.services.async_call.assert_not_awaited()


@pytest.mark.asyncio
async def test_scope_change_before_submission_blocks_purge() -> None:
    manager, hass = make_manager(False, PLAN.fingerprint)
    with patch(
        "custom_components.less_records.manager.preflight",
        side_effect=[PLAN, CHANGED],
    ):
        await manager.async_run()
    hass.services.async_call.assert_not_awaited()


@pytest.mark.asyncio
async def test_failed_recorder_service_is_logged_not_counted_as_deleted() -> None:
    manager, hass = make_manager(False, PLAN.fingerprint)
    hass.services.async_call.side_effect = RuntimeError("recorder error")
    with patch(
        "custom_components.less_records.manager.preflight", return_value=PLAN
    ):
        await manager.async_run()
    assert any(
        call.args[0] == "request_failed"
        for call in manager._audit.await_args_list
    )
    assert not any(
        call.args[0] == "request_submitted"
        for call in manager._audit.await_args_list
    )


def test_changed_scope_requires_approval() -> None:
    with pytest.raises(PolicyError, match="scope changed"):
        check_approval(CHANGED, False, PLAN.fingerprint)
    check_approval(CHANGED, True, "")


@pytest.mark.parametrize("invalid", ["invalid", "25:01:00", "12:61:00"])
def test_invalid_daily_time(invalid: str) -> None:
    with pytest.raises(PolicyError):
        normalize_run_time(invalid)


def test_valid_daily_time() -> None:
    assert normalize_run_time("06:30") == "06:30:00"


@pytest.mark.asyncio
async def test_overlapping_simulated_label_protects_live_label_entity() -> None:
    manager, hass = make_manager(False, PLAN.fingerprint)
    manager.entry.data["policies"] = {"a": 7, "b": 365}
    manager.entry.data["label_simulations"] = {"a": True, "b": False}
    manager._matching_label_ids = MagicMock(return_value={"a", "b"})
    plan = PurgePlan({365: ("sensor.one",)}, PLAN.fingerprint)
    with patch(
        "custom_components.less_records.manager.preflight", return_value=plan
    ):
        await manager.async_run()
    hass.services.async_call.assert_not_awaited()
    assert any(
        call.args[0] == "simulated"
        for call in manager._audit.await_args_list
    )


@pytest.mark.asyncio
async def test_boundary_uses_recorder_queue_not_standard_service() -> None:
    manager, hass = make_manager(False, PLAN.fingerprint)
    manager.entry.data["label_boundaries"] = {"a": True}
    with (
        patch(
            "custom_components.less_records.manager.preflight",
            return_value=PLAN,
        ),
        patch(
            "custom_components.less_records.manager.check_recorder"
        ) as recorder,
        patch(
            "custom_components.less_records.manager.queue_boundary_purge"
        ) as queued,
    ):
        await manager.async_run()
    hass.services.async_call.assert_not_awaited()
    queued.assert_called_once_with(
        recorder.return_value, ["sensor.one", "sensor.two"], 7
    )

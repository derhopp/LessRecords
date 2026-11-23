"""Scheduled, safety-first label-based Recorder purging."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, time, timedelta, timezone
import json
import logging
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er, label_registry as lr
from homeassistant.helpers.event import async_track_time_change

from .audit import append_audit
from .const import (
    AUDIT_FILENAME,
    BATCH_SIZE,
    CONF_APPROVED_FINGERPRINT,
    CONF_AUDIT_LOG,
    CONF_DRY_RUN,
    CONF_POLICIES,
    CONF_RUN_TIME,
    DEFAULT_AUDIT_LOG,
    DEFAULT_DRY_RUN,
    DEFAULT_RUN_TIME,
)
from .policy import PolicyError, PurgePlan, build_plan
from .recorder_guard import check_approval, check_recorder

_LOGGER = logging.getLogger(__name__)


def get_settings(entry: Any) -> dict[str, Any]:
    """Merge persisted setup and options values."""
    return {**entry.data, **entry.options}


def normalize_run_time(value: str) -> str:
    """Parse and validate a daily local time; use second precision."""
    try:
        parsed = time.fromisoformat(value)
    except (TypeError, ValueError) as err:
        raise PolicyError("Invalid daily purge time") from err
    if parsed.tzinfo is not None:
        raise PolicyError("Daily purge time must not contain a time zone offset")
    return parsed.replace(microsecond=0).isoformat()


def current_plan(hass: HomeAssistant, settings: dict[str, Any]) -> PurgePlan:
    """Build a deterministic snapshot from directly labeled entities."""
    label_registry = lr.async_get(hass)
    entity_registry = er.async_get(hass)
    return build_plan(
        settings[CONF_POLICIES],
        label_registry.labels.keys(),
        entity_registry.entities.values(),
    )


def preflight(hass: HomeAssistant, settings: dict[str, Any]) -> PurgePlan:
    """Check a plan and Recorder prerequisites without submitting any tasks."""
    normalize_run_time(settings.get(CONF_RUN_TIME, DEFAULT_RUN_TIME))
    plan = current_plan(hass, settings)
    check_recorder(hass, settings[CONF_POLICIES])
    return plan


class LessRecordsManager:
    """Own exactly one daily scheduled run for a config entry."""

    def __init__(self, hass: HomeAssistant, entry: Any) -> None:
        self.hass = hass
        self.entry = entry
        self._unsubscribe: Any = None
        self._lock = asyncio.Lock()
        self._last_run_date: date | None = None

    @callback
    def async_start(self) -> None:
        """Register local-time schedule; never purge at startup."""
        settings = get_settings(self.entry)
        schedule = time.fromisoformat(normalize_run_time(settings.get(
            CONF_RUN_TIME, DEFAULT_RUN_TIME
        )))

        @callback
        def _scheduled(now: datetime) -> None:
            today = now.date()
            if self._last_run_date == today:
                return
            self._last_run_date = today
            self.hass.async_create_task(self.async_run())

        self._unsubscribe = async_track_time_change(
            self.hass,
            _scheduled,
            hour=schedule.hour,
            minute=schedule.minute,
            second=schedule.second,
        )

    @callback
    def async_stop(self) -> None:
        """Remove the scheduler."""
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None

    async def _audit(self, action: str, **details: Any) -> None:
        """Audit each requested operation, or use HA logs when opted out."""
        record = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "action": action,
            **details,
        }
        settings = get_settings(self.entry)
        if settings.get(CONF_AUDIT_LOG, DEFAULT_AUDIT_LOG):
            await self.hass.async_add_executor_job(
                append_audit,
                self.hass.config.path(AUDIT_FILENAME),
                record,
            )
        else:
            _LOGGER.info("LessRecords audit (file disabled): %s", json.dumps(record))

    async def async_run(self) -> None:
        """Simulate or enqueue explicit Recorder purge_entities requests.

        Never directly modify the Recorder database. The Recorder service
        returns after queueing, not necessarily after deleting any rows.
        """
        if self._lock.locked():
            _LOGGER.warning("LessRecords run skipped: another run is active")
            return

        async with self._lock:
            settings = get_settings(self.entry)
            dry_run = settings.get(CONF_DRY_RUN, DEFAULT_DRY_RUN)
            if type(dry_run) is not bool:
                _LOGGER.error("LessRecords refused invalid simulation setting")
                return
            try:
                plan = preflight(self.hass, settings)
                check_approval(
                    plan,
                    dry_run,
                    settings.get(CONF_APPROVED_FINGERPRINT, ""),
                )
            except (PolicyError, KeyError, TypeError) as err:
                _LOGGER.error("LessRecords blocked run: %s", err)
                try:
                    await self._audit("blocked", reason=str(err), dry_run=dry_run)
                except OSError:
                    _LOGGER.exception("LessRecords audit failed while logging a blocked run")
                return

            if plan.count == 0:
                try:
                    await self._audit(
                        "no_targets", dry_run=dry_run, fingerprint=plan.fingerprint
                    )
                except OSError:
                    _LOGGER.exception("LessRecords could not write empty-plan audit")
                return

            for days, targets in sorted(plan.by_retention.items()):
                for offset in range(0, len(targets), BATCH_SIZE):
                    batch = list(targets[offset : offset + BATCH_SIZE])
                    if not dry_run:
                        try:
                            # Scope and Recorder must still be safe just before
                            # each destructive submission.
                            fresh = preflight(self.hass, get_settings(self.entry))
                            check_approval(
                                fresh,
                                False,
                                settings.get(CONF_APPROVED_FINGERPRINT, ""),
                            )
                            if fresh.fingerprint != plan.fingerprint:
                                raise PolicyError("Target scope changed during this run")
                            if any(
                                entity_id not in fresh.by_retention.get(days, ())
                                for entity_id in batch
                            ):
                                raise PolicyError("A target changed retention during this run")
                        except (PolicyError, KeyError, TypeError) as err:
                            _LOGGER.error("LessRecords aborted before batch: %s", err)
                            try:
                                await self._audit("blocked", reason=str(err), dry_run=False)
                            except OSError:
                                _LOGGER.exception("LessRecords audit failed")
                            return

                    context = {
                        "dry_run": dry_run,
                        "entities": batch,
                        "keep_days": days,
                        "cutoff_utc_approx": (
                            datetime.now(timezone.utc) - timedelta(days=days)
                        ).isoformat(),
                        "fingerprint": plan.fingerprint,
                    }
                    try:
                        # Fail closed on an unwritable enabled audit trail:
                        # the *intent* must be persisted before submission.
                        await self._audit(
                            "simulated" if dry_run else "request_pending",
                            **context,
                        )
                    except OSError:
                        _LOGGER.exception(
                            "LessRecords stopped: the audit file is not writable"
                        )
                        return

                    if dry_run:
                        continue

                    try:
                        await self.hass.services.async_call(
                            "recorder",
                            "purge_entities",
                            {"entity_id": batch, "keep_days": days},
                            blocking=True,
                        )
                    except Exception:
                        _LOGGER.exception("LessRecords Recorder submission failed")
                        try:
                            await self._audit("request_failed", **context)
                        except OSError:
                            _LOGGER.exception("LessRecords could not record request failure")
                        return

                    # Only confirms the service request was accepted/queued.
                    try:
                        await self._audit("request_submitted", **context)
                    except OSError:
                        _LOGGER.exception(
                            "LessRecords request was submitted but post-audit failed"
                        )

            _LOGGER.info(
                "LessRecords %s finished: %s target entities; no deleted-row "
                "count is available",
                "simulation" if dry_run else "request submission",
                plan.count,
            )

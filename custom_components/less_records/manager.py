"""Daily Recorder orchestration, one label device per retention policy."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, time, timezone
import json
import logging
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er, label_registry as lr
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.storage import Store

from .audit import append_audit
from .boundary import queue_boundary_purge
from .const import (
    AUDIT_FILENAME,
    BATCH_SIZE,
    CONF_APPROVED_FINGERPRINT,
    CONF_AUDIT_LOG,
    CONF_DRY_RUN,
    CONF_POLICIES,
    CONF_RUN_TIME,
    DEFAULT_AUDIT_LOG,
    DEFAULT_RUN_TIME,
    DOMAIN,
    STATE_STORE_VERSION,
)
from .policy import PolicyError, PurgePlan, build_plan, validate_policies
from .recorder_guard import check_approval, check_recorder

_LOGGER = logging.getLogger(__name__)


def get_settings(entry: Any) -> dict[str, Any]:
    """Merge configuration and options, including migrated per-label settings."""
    return {**entry.data, **entry.options}


def normalize_run_time(value: str) -> str:
    """Check a local clock time without converting into a UTC timestamp."""
    try:
        parsed = time.fromisoformat(value)
    except (TypeError, ValueError) as err:
        raise PolicyError("Invalid daily purge time") from err
    if parsed.tzinfo is not None:
        raise PolicyError("Daily purge time must not contain a UTC offset")
    return parsed.replace(microsecond=0).isoformat()


def current_plan(hass: HomeAssistant, settings: dict[str, Any]) -> PurgePlan:
    """Compute the effective longest-retention rule for each labeled entity."""
    return build_plan(
        settings[CONF_POLICIES],
        lr.async_get(hass).labels.keys(),
        er.async_get(hass).entities.values(),
    )


def preflight(hass: HomeAssistant, settings: dict[str, Any]) -> PurgePlan:
    """All destructive paths require this validation."""
    normalize_run_time(settings.get(CONF_RUN_TIME, DEFAULT_RUN_TIME))
    plan = current_plan(hass, settings)
    check_recorder(hass, settings[CONF_POLICIES])
    return plan


def targets_for_policy(hass: HomeAssistant, label_id: str) -> tuple[set[str], set[str]]:
    """Return directly labeled entities and unique physical device IDs."""
    entities = set()
    devices = set()
    for entry in er.async_get(hass).entities.values():
        if entry.disabled_by is not None or label_id not in (entry.labels or set()):
            continue
        entities.add(entry.entity_id)
        if entry.device_id:
            devices.add(entry.device_id)
    return entities, devices


class LessRecordsManager:
    """Own the global scheduler, per-label run state and audit notifications."""

    def __init__(self, hass: HomeAssistant, entry: Any) -> None:
        self.hass = hass
        self.entry = entry
        self._unsubscribe: Any = None
        self._lock = asyncio.Lock()
        self._last_run_date: date | None = None
        self._store: Store = Store(hass, STATE_STORE_VERSION, f"{DOMAIN}.{entry.entry_id}")
        self.status: dict[str, dict[str, str | None]] = {}
        self.last_audit: dict[str, Any] = {}
        self.signal = f"{DOMAIN}_update_{entry.entry_id}"

    async def async_load(self) -> None:
        """Restore timestamp sensors across Home Assistant restarts."""
        data = await self._store.async_load()
        if isinstance(data, dict):
            self.status = {
                label: values
                for label, values in data.get("status", {}).items()
                if isinstance(label, str) and isinstance(values, dict)
            }
            self.last_audit = data.get("last_audit", {})

    async def _persist(self) -> None:
        await self._store.async_save(
            {"status": self.status, "last_audit": self.last_audit}
        )
        async_dispatcher_send(self.hass, self.signal)

    @callback
    def async_start(self) -> None:
        """Schedule exactly one callback per day in HA's local timezone."""
        settings = get_settings(self.entry)
        schedule = time.fromisoformat(
            normalize_run_time(settings.get(CONF_RUN_TIME, DEFAULT_RUN_TIME))
        )

        @callback
        def _scheduled(now: datetime) -> None:
            if now.date() == self._last_run_date:
                return
            self._last_run_date = now.date()
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
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None

    async def _audit(self, action: str, **details: Any) -> None:
        """Persist a machine-readable audit entry before any live request."""
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
        self.last_audit = record
        async_dispatcher_send(self.hass, self.signal)

    def _matching_label_ids(self, entity_id: str, policies: dict[str, int]) -> set[str]:
        entry = er.async_get(self.hass).async_get(entity_id)
        if entry is None:
            raise PolicyError(f"Entity removed from registry: {entity_id}")
        return set(entry.labels or ()) & policies.keys()

    async def async_run(self) -> None:
        """Execute label-specific simulations or bounded Recorder queue jobs.

        Any label in simulation prevents *all* deletions for an entity bearing
        that label, including overlapping-label entities. Longest retention
        still wins whenever a live purge is permitted.
        """
        from .settings import boundary_enabled, is_simulation

        if self._lock.locked():
            _LOGGER.warning("LessRecords skipped concurrent run")
            return

        async with self._lock:
            settings = get_settings(self.entry)
            # Even a blocked run is a scheduled attempt and must appear in
            # each purge-device's Last run sensor.
            tentative = settings.get(CONF_POLICIES)
            if isinstance(tentative, dict):
                attempted_at = datetime.now(timezone.utc).isoformat()
                for label_id in tentative:
                    if isinstance(label_id, str):
                        self.status.setdefault(label_id, {})["last_run"] = attempted_at
            try:
                policies = validate_policies(settings[CONF_POLICIES])
                plan = preflight(self.hass, settings)
            except (KeyError, TypeError, PolicyError) as err:
                _LOGGER.error("LessRecords blocked run: %s", err)
                try:
                    await self._audit("blocked", reason=str(err))
                except OSError:
                    _LOGGER.exception("Audit of blocked purge failed")
                await self._persist()
                return

            # An approval must be checked for the exact current scope
            # whenever *any* policy is about to execute in live mode.
            any_live = any(not is_simulation(settings, label) for label in policies)
            if any_live:
                if settings.get(CONF_DRY_RUN) is not False:
                    await self._audit(
                        "blocked", reason="Global live approval is missing"
                    )
                    await self._persist()
                    return
                try:
                    check_approval(
                        plan, bool(settings.get(CONF_DRY_RUN, True)),
                        settings.get(CONF_APPROVED_FINGERPRINT, ""),
                    )
                except PolicyError as err:
                    await self._audit("blocked", reason=str(err))
                    await self._persist()
                    return

            for days, entities in plan.by_retention.items():
                # Batch by *actual* policy behavior, including boundary setting.
                groups: dict[tuple[bool, bool], list[tuple[str, list[str]]]] = {}
                for entity_id in entities:
                    matches = sorted(self._matching_label_ids(entity_id, policies))
                    if not matches:
                        await self._audit(
                            "blocked", reason="An entity lost its configured labels"
                        )
                        await self._persist()
                        return
                    simulation = any(is_simulation(settings, label) for label in matches)
                    preserve = any(boundary_enabled(settings, label) for label in matches)
                    groups.setdefault((simulation, preserve), []).append(
                        (entity_id, matches)
                    )

                for (simulation, preserve), items in groups.items():
                    for offset in range(0, len(items), BATCH_SIZE):
                        batch_items = items[offset : offset + BATCH_SIZE]
                        batch = [entity_id for entity_id, _ in batch_items]
                        affected_labels = sorted(
                            {label for _, matches in batch_items for label in matches}
                        )

                        if not simulation:
                            try:
                                current_settings = get_settings(self.entry)
                                fresh = preflight(self.hass, current_settings)
                                check_approval(
                                    fresh,
                                    bool(current_settings.get(CONF_DRY_RUN, True)),
                                    current_settings.get(CONF_APPROVED_FINGERPRINT, ""),
                                )
                                if fresh.fingerprint != plan.fingerprint:
                                    raise PolicyError("Scope changed during the run")
                                if any(
                                    is_simulation(current_settings, label)
                                    for label in affected_labels
                                ):
                                    raise PolicyError("Simulation mode changed during the run")
                                for entity_id, matches in batch_items:
                                    if (
                                        entity_id not in fresh.by_retention.get(days, ())
                                        or self._matching_label_ids(
                                            entity_id, policies
                                        ) != set(matches)
                                    ):
                                        raise PolicyError("Target labels changed during the run")
                            except (KeyError, PolicyError, TypeError) as err:
                                _LOGGER.error("LessRecords aborted: %s", err)
                                await self._audit("blocked", reason=str(err))
                                await self._persist()
                                return

                        context = {
                            "entities": batch,
                            "labels": affected_labels,
                            "keep_days": days,
                            "dry_run": simulation,
                            "preserve_boundary": preserve,
                            "fingerprint": plan.fingerprint,
                        }
                        try:
                            await self._audit(
                                "simulated" if simulation else "request_pending",
                                **context,
                            )
                        except OSError:
                            _LOGGER.exception("Audit unwritable: purge blocked")
                            await self._persist()
                            return
                        if simulation:
                            continue

                        try:
                            if preserve:
                                # Recorder-internal queue task ensures that
                                # historic anchor insertion and entity purge
                                # are serialized on the Recorder worker.
                                recorder = check_recorder(self.hass, policies)
                                queue_boundary_purge(recorder, batch, days)
                            else:
                                await self.hass.services.async_call(
                                    "recorder",
                                    "purge_entities",
                                    {"entity_id": batch, "keep_days": days},
                                    blocking=True,
                                )
                        except Exception:
                            _LOGGER.exception("LessRecords Recorder submission failed")
                            await self._audit("request_failed", **context)
                            await self._persist()
                            return

                        for label in affected_labels:
                            self.status.setdefault(label, {})["last_purge_run"] = (
                                datetime.now(timezone.utc).isoformat()
                            )
                        try:
                            await self._audit("request_submitted", **context)
                        except OSError:
                            _LOGGER.exception("Recorder job queued but post-audit failed")
            await self._persist()

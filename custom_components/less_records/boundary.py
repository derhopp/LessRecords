"""Recorder-thread-only SQLite retention-boundary preservation.

This is a deliberate use of Home Assistant's internal Recorder task API.
It must not be used on unsupported Recorder implementations. The task
inserts historical anchor rows and runs the matching purge on the *same*
Recorder worker, never mutating Home Assistant's live state machine.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging

from sqlalchemy import select

from homeassistant.components.recorder.db_schema import States, StatesMeta
from homeassistant.components.recorder.tasks import PurgeEntitiesTask, RecorderTask
from homeassistant.helpers.recorder import session_scope

_LOGGER = logging.getLogger(__name__)

# The anchor is strictly newer than Recorder's purge cutoff. This margin
# must exceed time between queue submission and task processing.
BOUNDARY_MARGIN = timedelta(seconds=30)
MAX_ANCHOR_ENTITIES = 100


class BoundaryError(RuntimeError):
    """A Recorder boundary operation cannot be performed safely."""


def create_boundary_states(
    session,
    entity_ids: tuple[str, ...],
    purge_before: datetime,
) -> int:
    """Copy last discarded state to retention boundary with isolated references.

    All writes are within Recorder's own SQLAlchemy session and recorder thread.
    Never rewrite last_changed/live state, statistics, or another state row.
    """
    if not 0 < len(entity_ids) <= MAX_ANCHOR_ENTITIES:
        raise BoundaryError("Invalid number of state preservation targets")
    if purge_before.tzinfo is None:
        raise BoundaryError("A timezone-aware cutoff is required")
    cutoff = purge_before.timestamp()
    anchor_time = (purge_before + BOUNDARY_MARGIN).timestamp()
    inserted = 0
    for entity_id in entity_ids:
        metadata_id = session.scalar(
            select(StatesMeta.metadata_id).where(StatesMeta.entity_id == entity_id)
        )
        if metadata_id is None:
            continue
        # Exactly one historical source, the newest row to be deleted.
        source = session.scalar(
            select(States)
            .where(
                States.metadata_id == metadata_id,
                States.last_updated_ts < cutoff,
            )
            .order_by(States.last_updated_ts.desc(), States.state_id.desc())
            .limit(1)
        )
        if source is None or source.state in (None, "unknown", "unavailable"):
            continue
        # Avoid manufacturing duplicates if Recorder already has a state
        # at the boundary (including an anchor from an earlier retry).
        existing = session.scalar(
            select(States.state_id)
            .where(
                States.metadata_id == metadata_id,
                States.last_updated_ts >= cutoff,
                States.last_updated_ts <= anchor_time,
            )
            .limit(1)
        )
        if existing is not None:
            continue
        session.add(
            States(
                metadata_id=metadata_id,
                state=source.state,
                attributes_id=source.attributes_id,
                last_changed_ts=anchor_time,
                last_updated_ts=anchor_time,
                last_reported_ts=anchor_time,
                old_state_id=None,
                context_id_bin=None,
            )
        )
        inserted += 1
    return inserted


@dataclass(slots=True)
class BoundaryPurgeTask(RecorderTask):
    """First store synthetic anchors, then purge in Recorder's own thread."""

    entity_ids: tuple[str, ...]
    purge_before: datetime

    def run(self, instance) -> None:
        """Fail closed: never purge when synthetic-state insertion fails."""
        if not str(getattr(instance, "db_url", "")).startswith("sqlite:///"):
            _LOGGER.error("Boundary purge refused unsupported Recorder database")
            return
        try:
            with session_scope(session=instance.get_session()) as session:
                inserted = create_boundary_states(
                    session, self.entity_ids, self.purge_before
                )
            _LOGGER.info(
                "Created %s historical retention-boundary state(s) for %s targets",
                inserted,
                len(self.entity_ids),
            )
        except Exception:
            _LOGGER.exception(
                "LessRecords preservation failed: purge NOT executed for this batch"
            )
            return

        allowed = frozenset(self.entity_ids)
        PurgeEntitiesTask(
            lambda entity_id: entity_id in allowed,
            self.purge_before,
        ).run(instance)


def queue_boundary_purge(recorder, entity_ids: list[str], keep_days: int) -> None:
    """Submit a bounded preservation/purge task through Recorder's own queue."""
    if not entity_ids or len(entity_ids) > MAX_ANCHOR_ENTITIES:
        raise BoundaryError("Invalid retention-boundary target count")
    if type(keep_days) is not int or keep_days < 1:
        raise BoundaryError("Invalid retention for boundary task")
    if not str(getattr(recorder, "db_url", "")).startswith("sqlite:///"):
        raise BoundaryError("Only SQLite Recorder supports boundary preservation")
    cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)
    recorder.queue_task(BoundaryPurgeTask(tuple(entity_ids), cutoff))

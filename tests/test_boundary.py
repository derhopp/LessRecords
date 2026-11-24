"""Disposable SQLite regression tests: boundary preservation never touches live state."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import Float, ForeignKey, Integer, String, create_engine, delete, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from custom_components.less_records import boundary


class Base(DeclarativeBase):
    pass


class StatesMeta(Base):
    __tablename__ = "states_meta"
    metadata_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_id: Mapped[str] = mapped_column(String, unique=True)


class States(Base):
    __tablename__ = "states"
    state_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    metadata_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("states_meta.metadata_id")
    )
    state: Mapped[str] = mapped_column(String)
    attributes_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_changed_ts: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_updated_ts: Mapped[float] = mapped_column(Float)
    last_reported_ts: Mapped[float | None] = mapped_column(Float, nullable=True)
    old_state_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    context_id_bin: Mapped[bytes | None] = mapped_column(nullable=True)


@pytest.fixture
def db(monkeypatch):
    """Isolate the retention algorithm on a disposable, realistic SQLite schema."""
    monkeypatch.setattr(boundary, "States", States)
    monkeypatch.setattr(boundary, "StatesMeta", StatesMeta)
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all(
            [
                StatesMeta(metadata_id=1, entity_id="sensor.sparse"),
                StatesMeta(metadata_id=2, entity_id="sensor.fresh"),
                StatesMeta(metadata_id=3, entity_id="sensor.unavailable"),
            ]
        )
        session.commit()
        yield session
    engine.dispose()


def seed(db, meta_id: int, state: str, timestamp: float) -> None:
    db.add(
        States(
            metadata_id=meta_id,
            state=state,
            attributes_id=None,
            last_updated_ts=timestamp,
            last_changed_ts=timestamp,
        )
    )
    db.commit()


def values(db, meta_id: int):
    return db.scalars(
        select(States)
        .where(States.metadata_id == meta_id)
        .order_by(States.last_updated_ts)
    ).all()


def test_sparse_state_gets_one_anchor_after_purge_without_affecting_others(db):
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    ts = cutoff.timestamp()
    seed(db, 1, "16.1", ts - 300 * 86400)
    seed(db, 1, "17.4", ts - 31)
    seed(db, 2, "22.0", ts + 86400)

    assert boundary.create_boundary_states(db, ("sensor.sparse",), cutoff) == 1
    db.commit()
    db.execute(delete(States).where(States.last_updated_ts < ts))
    db.commit()

    sparse = values(db, 1)
    assert len(sparse) == 1
    assert sparse[0].state == "17.4"
    assert sparse[0].last_updated_ts > ts
    assert values(db, 2)[0].state == "22.0"


def test_anchor_is_idempotent_in_boundary_window(db):
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    seed(db, 1, "11", cutoff.timestamp() - 200)
    assert boundary.create_boundary_states(db, ("sensor.sparse",), cutoff) == 1
    db.commit()
    assert boundary.create_boundary_states(db, ("sensor.sparse",), cutoff) == 0


def test_unknown_and_unavailable_values_are_not_fabricated(db):
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    seed(db, 3, "unavailable", cutoff.timestamp() - 30)
    assert (
        boundary.create_boundary_states(db, ("sensor.unavailable",), cutoff) == 0
    )


@pytest.mark.parametrize("targets", [(), ("sensor.sparse",) * 101])
def test_scope_limit_fails_closed(db, targets):
    with pytest.raises(boundary.BoundaryError):
        boundary.create_boundary_states(db, targets, datetime.now(timezone.utc))


def test_no_anchor_without_pre_cutoff_state(db):
    assert (
        boundary.create_boundary_states(
            db, ("sensor.sparse",), datetime.now(timezone.utc)
        ) == 0
    )

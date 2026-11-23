"""Pure retention planning tests; no database can be touched."""

from dataclasses import dataclass, field

import pytest

from custom_components.less_records.policy import (
    PolicyError,
    build_plan,
    validate_policies,
)


@dataclass
class RegistryEntity:
    entity_id: str
    labels: frozenset[str] = field(default_factory=frozenset)
    disabled_by: str | None = None


def test_at_least_one_label_is_required() -> None:
    with pytest.raises(PolicyError, match="At least one"):
        validate_policies({})


@pytest.mark.parametrize("days", [0, -1, 3651, 1.5, True, "7", None])
def test_invalid_retention_is_rejected(days: object) -> None:
    with pytest.raises(PolicyError):
        validate_policies({"short": days})


def test_single_label_and_unmatched_entities() -> None:
    plan = build_plan(
        {"short": 7},
        {"short"},
        [
            RegistryEntity("sensor.kitchen", frozenset({"short"})),
            RegistryEntity("sensor.unlabeled"),
            RegistryEntity("sensor.other", frozenset({"other"})),
        ],
    )
    assert plan.by_retention == {7: ("sensor.kitchen",)}
    assert plan.count == 1


def test_longest_matching_retention_wins_without_duplicates() -> None:
    plan = build_plan(
        {"short": 7, "critical": 365, "mid": 30},
        {"short", "critical", "mid"},
        [
            RegistryEntity("sensor.a", frozenset({"short", "critical"})),
            RegistryEntity("sensor.b", frozenset({"mid"})),
            RegistryEntity("sensor.c", frozenset({"short"})),
        ],
    )
    assert plan.by_retention == {
        7: ("sensor.c",),
        30: ("sensor.b",),
        365: ("sensor.a",),
    }
    assert plan.count == 3


def test_disabled_entities_are_not_purged() -> None:
    plan = build_plan(
        {"short": 7},
        {"short"},
        [RegistryEntity("sensor.disabled", frozenset({"short"}), "user")],
    )
    assert plan.count == 0


def test_missing_label_aborts_entire_run() -> None:
    with pytest.raises(PolicyError, match="no longer exist"):
        build_plan({"deleted": 7}, {"other"}, [])


def test_corrupt_registry_entry_aborts_entire_run() -> None:
    with pytest.raises(PolicyError, match="Invalid entity ID"):
        build_plan(
            {"short": 7},
            {"short"},
            [RegistryEntity("sensor.*", frozenset({"short"}))],
        )


def test_fingerprint_is_deterministic_and_detects_scope_changes() -> None:
    first = RegistryEntity("sensor.one", frozenset({"short"}))
    second = RegistryEntity("sensor.two", frozenset({"short"}))
    baseline = build_plan({"short": 7}, {"short"}, [first])
    assert baseline.fingerprint == build_plan(
        {"short": 7}, {"short"}, [first]
    ).fingerprint
    assert baseline.fingerprint != build_plan(
        {"short": 7}, {"short"}, [first, second]
    ).fingerprint
    assert baseline.fingerprint != build_plan(
        {"short": 6}, {"short"}, [first]
    ).fingerprint


def test_large_target_scope_is_rejected() -> None:
    entities = [
        RegistryEntity(f"sensor.target_{index}", frozenset({"short"}))
        for index in range(1501)
    ]
    with pytest.raises(PolicyError, match="Safety limit"):
        build_plan({"short": 7}, {"short"}, entities)

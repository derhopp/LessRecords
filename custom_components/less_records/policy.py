"""Pure, deterministic and fail-closed LessRecords retention planning."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any, Iterable, Mapping

from .const import MAX_ENTITIES, MAX_KEEP_DAYS

ENTITY_ID_RE = re.compile(r"^[a-z0-9_]+\.[a-z0-9_]+$")


class PolicyError(ValueError):
    """An unsafe or invalid retention policy."""


@dataclass(frozen=True)
class PurgePlan:
    """A snapshot of explicitly targeted entities and their retention."""

    by_retention: dict[int, tuple[str, ...]]
    fingerprint: str

    @property
    def count(self) -> int:
        """Return the number of unique targeted entities."""
        return sum(len(entity_ids) for entity_ids in self.by_retention.values())


def validate_policies(policies: Mapping[str, Any]) -> dict[str, int]:
    """Validate label IDs and integer retention days without coercion."""
    if not isinstance(policies, dict) or not policies:
        raise PolicyError("At least one label retention policy is required")
    validated: dict[str, int] = {}
    for label_id, days in policies.items():
        if not isinstance(label_id, str) or not label_id.strip():
            raise PolicyError("Invalid label ID")
        if type(days) is not int or not 1 <= days <= MAX_KEEP_DAYS:
            raise PolicyError(f"Invalid retention for label {label_id}")
        validated[label_id] = days
    return validated


def build_plan(
    policies: Mapping[str, Any],
    known_label_ids: Iterable[str],
    registry_entries: Iterable[Any],
) -> PurgePlan:
    """Resolve direct entity labels, using the longest retention for overlaps.

    Disabled entities are skipped. Unknown configured labels and malformed
    registry entries always abort planning rather than widening the scope.
    """
    validated = validate_policies(policies)
    if unknown := set(validated) - set(known_label_ids):
        raise PolicyError(f"Configured label IDs no longer exist: {sorted(unknown)}")

    resolved: dict[str, int] = {}
    for entry in registry_entries:
        entity_id = getattr(entry, "entity_id", None)
        labels = getattr(entry, "labels", None)
        if not isinstance(entity_id, str) or labels is None:
            raise PolicyError("Invalid entity registry entry")
        if not ENTITY_ID_RE.fullmatch(entity_id):
            raise PolicyError(f"Invalid entity ID: {entity_id}")
        if getattr(entry, "disabled_by", None) is not None:
            continue
        if not isinstance(labels, (set, frozenset)):
            raise PolicyError(f"Invalid labels on {entity_id}")
        matches = validated.keys() & labels
        if matches:
            resolved[entity_id] = max(validated[label] for label in matches)

    if len(resolved) > MAX_ENTITIES:
        raise PolicyError(
            f"Safety limit exceeded: {len(resolved)} targeted entities "
            f"(maximum {MAX_ENTITIES})"
        )
    grouped: dict[int, list[str]] = {}
    for entity_id, days in sorted(resolved.items()):
        grouped.setdefault(days, []).append(entity_id)

    snapshot = {
        "policies": sorted(validated.items()),
        "targets": sorted(resolved.items()),
    }
    fingerprint = hashlib.sha256(
        json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return PurgePlan(
        by_retention={days: tuple(ids) for days, ids in sorted(grouped.items())},
        fingerprint=fingerprint,
    )

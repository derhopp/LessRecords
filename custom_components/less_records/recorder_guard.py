"""Home Assistant Recorder preflight guards — never write Recorder SQL."""

from __future__ import annotations

from typing import Any, Mapping

from homeassistant.helpers.recorder import DATA_INSTANCE

from .policy import PolicyError, PurgePlan, validate_policies


def check_recorder(hass: Any, policies: Mapping[str, int]) -> Any:
    """Reject unsupported or unsafe Recorder states before a purge request.

    Keep the system's own auto-purge enabled and require its global retention
    to be no shorter than the longest LessRecords label retention.
    """
    validated = validate_policies(policies)
    instance = hass.data.get(DATA_INSTANCE)
    if instance is None:
        raise PolicyError("Recorder is unavailable")
    if not isinstance(getattr(instance, "db_url", None), str) or not (
        instance.db_url.startswith("sqlite:///")
    ):
        raise PolicyError("Only SQLite Recorder databases are supported in v1")
    if getattr(instance, "auto_purge", None) is not True:
        raise PolicyError("Recorder's global auto_purge must remain enabled")
    if type(getattr(instance, "keep_days", None)) is not int or (
        instance.keep_days < max(validated.values())
    ):
        raise PolicyError(
            "Recorder purge_keep_days must be at least the longest label retention"
        )
    if (
        not getattr(instance, "is_running", False)
        or getattr(instance, "engine", None) is None
        or getattr(instance, "migration_in_progress", False)
        or not getattr(instance, "enabled", False)
    ):
        raise PolicyError("Recorder is not ready for a purge")
    if not hass.services.has_service("recorder", "purge_entities"):
        raise PolicyError("Recorder purge_entities service is unavailable")
    return instance


def check_approval(plan: PurgePlan, dry_run: bool, approved_fingerprint: str) -> None:
    """Require an exact reviewed entity/policy scope before live operations."""
    if dry_run:
        return
    if not approved_fingerprint or approved_fingerprint != plan.fingerprint:
        raise PolicyError(
            "The target scope changed after approval; switch to simulation "
            "and review the current scope before re-activating"
        )

"""Safe, atomic policy editing and per-label settings shared by all HA entities."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import label_registry as lr

from .const import (
    CONF_APPROVED_FINGERPRINT,
    CONF_DRY_RUN,
    CONF_LABEL_BOUNDARIES,
    CONF_LABEL_SIMULATIONS,
    CONF_POLICIES,
    CONF_POLICY_IDS,
    MAX_KEEP_DAYS,
)
from .manager import current_plan, get_settings
from .policy import PolicyError, validate_policies


def stable_id(settings: Mapping[str, Any], label_id: str) -> str:
    """Keep a device's identity when its target label changes."""
    return settings.get(CONF_POLICY_IDS, {}).get(label_id, f"label_{label_id}")


def is_simulation(settings: Mapping[str, Any], label_id: str) -> bool:
    """Legacy migration: missing per-label setting inherits global mode."""
    return bool(settings.get(CONF_LABEL_SIMULATIONS, {}).get(label_id, True))


def boundary_enabled(settings: Mapping[str, Any], label_id: str) -> bool:
    """Boundary injection must be explicitly opted into per label."""
    return settings.get(CONF_LABEL_BOUNDARIES, {}).get(label_id) is True


def reset_approval(settings: dict[str, Any]) -> dict[str, Any]:
    """Reset ALL label switches to simulation after a policy/anchor change."""
    policies = validate_policies(settings[CONF_POLICIES])
    settings[CONF_DRY_RUN] = True
    settings[CONF_APPROVED_FINGERPRINT] = ""
    settings[CONF_LABEL_SIMULATIONS] = dict.fromkeys(policies, True)
    return settings


async def async_update_policy(
    hass: Any,
    entry: Any,
    label_id: str,
    *,
    days: int | None = None,
    new_label_id: str | None = None,
    boundary: bool | None = None,
) -> None:
    """Change one policy, preserving other policies and revoking destructive approval."""
    settings = get_settings(entry)
    policies = validate_policies(settings[CONF_POLICIES])
    if label_id not in policies:
        raise HomeAssistantError("The selected label policy no longer exists")
    if days is not None:
        if type(days) is not int or not 1 <= days <= MAX_KEEP_DAYS:
            raise HomeAssistantError("Retention must be 1–3650 whole days")
    if new_label_id is not None:
        known = lr.async_get(hass).labels
        if new_label_id not in known:
            raise HomeAssistantError("The selected Home Assistant label no longer exists")
        if new_label_id != label_id and new_label_id in policies:
            raise HomeAssistantError("This label already has a retention policy")
    target = new_label_id or label_id
    old_days = policies[label_id]
    old_boundary = boundary_enabled(settings, label_id)
    if target == label_id and (days is None or days == old_days) and (
        boundary is None or boundary == old_boundary
    ):
        return

    new_settings = dict(settings)
    new_policies = dict(policies)
    new_policies.pop(label_id)
    new_policies[target] = days if days is not None else old_days
    new_settings[CONF_POLICIES] = validate_policies(new_policies)

    ids = {key: stable_id(settings, key) for key in policies}
    policy_id = ids.pop(label_id)
    ids[target] = policy_id
    new_settings[CONF_POLICY_IDS] = ids

    old_boundaries = dict(settings.get(CONF_LABEL_BOUNDARIES, {}))
    previous_boundary = old_boundaries.pop(label_id, False)
    old_boundaries[target] = previous_boundary if boundary is None else boundary
    new_settings[CONF_LABEL_BOUNDARIES] = old_boundaries

    reset_approval(new_settings)
    hass.config_entries.async_update_entry(entry, options=new_settings)


async def async_set_simulation(hass: Any, entry: Any, label_id: str, enabled: bool) -> None:
    """Switch one policy. Live mode requires an existing, matching approval."""
    settings = get_settings(entry)
    if label_id not in validate_policies(settings[CONF_POLICIES]):
        raise HomeAssistantError("The label is no longer configured")
    if not enabled:
        if settings.get(CONF_DRY_RUN, True) is not False:
            raise HomeAssistantError(
                "Live purge is not approved. Open LessRecords options and review "
                "the target scope before disabling simulation."
            )
        try:
            plan = current_plan(hass, settings)
        except (PolicyError, KeyError, TypeError) as err:
            raise HomeAssistantError(f"Invalid current purge scope: {err}") from err
        if settings.get(CONF_APPROVED_FINGERPRINT) != plan.fingerprint:
            raise HomeAssistantError(
                "The affected entity scope changed; review and approve it again."
            )
    simulations = dict(settings.get(CONF_LABEL_SIMULATIONS, {}))
    simulations[label_id] = enabled
    if enabled == is_simulation(settings, label_id):
        return
    hass.config_entries.async_update_entry(
        entry,
        options={**settings, CONF_LABEL_SIMULATIONS: simulations},
    )

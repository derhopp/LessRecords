"""English/German UI setup and safely reviewed options for LessRecords."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import label_registry as lr, selector

from .const import (
    CONF_APPROVED_FINGERPRINT,
    CONF_AUDIT_LOG,
    CONF_DRY_RUN,
    CONF_POLICIES,
    CONF_RUN_TIME,
    DEFAULT_AUDIT_LOG,
    DEFAULT_DRY_RUN,
    DEFAULT_RUN_TIME,
    DOMAIN,
    MAX_KEEP_DAYS,
)
from .manager import get_settings, normalize_run_time, preflight
from .policy import PolicyError, validate_policies

CONF_LABEL = "label"
CONF_KEEP_DAYS = "keep_days"
CONF_ADD_ANOTHER = "add_another"
CONF_ACKNOWLEDGE = "acknowledge"

_LABEL_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_LABEL): selector.LabelSelector(
            selector.LabelSelectorConfig(multiple=False)
        ),
        vol.Required(CONF_KEEP_DAYS, default=30): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=1, max=MAX_KEEP_DAYS, step=1,
                mode=selector.NumberSelectorMode.BOX
            )
        ),
        vol.Required(CONF_ADD_ANOTHER, default=False): bool,
    }
)

_ACK_SCHEMA = vol.Schema({vol.Required(CONF_ACKNOWLEDGE, default=False): bool})


def _parse_retention(value: Any) -> int:
    """Refuse fractional, boolean, negative, or unbounded retention."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PolicyError("Retention must be an integer number of days")
    if int(value) != value or not 1 <= value <= MAX_KEEP_DAYS:
        raise PolicyError("Retention must be a whole number of valid days")
    return int(value)


class LessRecordsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Initial setup always creates a non-destructive simulation."""

    VERSION = 1

    def __init__(self) -> None:
        self._settings: dict[str, Any] = {}
        self._policies: dict[str, int] = {}

    async def async_step_user(self, user_input: dict | None = None):
        """Choose global time and optional dedicated audit logging."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors = {}
        if user_input is not None:
            try:
                run_time = normalize_run_time(user_input[CONF_RUN_TIME])
            except (KeyError, PolicyError):
                errors["base"] = "invalid_time"
            else:
                self._settings = {
                    CONF_RUN_TIME: run_time,
                    CONF_AUDIT_LOG: user_input[CONF_AUDIT_LOG],
                }
                return await self.async_step_label()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_RUN_TIME, default=DEFAULT_RUN_TIME
                    ): selector.TimeSelector(),
                    vol.Required(
                        CONF_AUDIT_LOG, default=DEFAULT_AUDIT_LOG
                    ): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_label(self, user_input: dict | None = None):
        """Build any number of unique label/retention pairs."""
        errors = {}
        if user_input is not None:
            label_id = user_input[CONF_LABEL]
            try:
                days = _parse_retention(user_input[CONF_KEEP_DAYS])
                if label_id not in lr.async_get(self.hass).labels:
                    errors["base"] = "unknown_label"
                elif label_id in self._policies:
                    errors[CONF_LABEL] = "duplicate_label"
                else:
                    self._policies[label_id] = days
                    if user_input[CONF_ADD_ANOTHER]:
                        return await self.async_step_label()
                    return await self.async_step_warning()
            except (KeyError, PolicyError, TypeError, ValueError):
                errors["base"] = "invalid_retention"
        return self.async_show_form(
            step_id="label", data_schema=_LABEL_SCHEMA, errors=errors
        )

    async def async_step_warning(self, user_input: dict | None = None):
        """Require acknowledgement even though initial setup is dry-run."""
        errors = {}
        if user_input is not None:
            if not user_input.get(CONF_ACKNOWLEDGE, False):
                errors["base"] = "acknowledgement_required"
            else:
                try:
                    validate_policies(self._policies)
                except PolicyError:
                    errors["base"] = "invalid_retention"
                else:
                    return self.async_create_entry(
                        title="LessRecords",
                        data={
                            **self._settings,
                            CONF_POLICIES: self._policies,
                            CONF_DRY_RUN: DEFAULT_DRY_RUN,
                            CONF_APPROVED_FINGERPRINT: "",
                        },
                    )
        return self.async_show_form(
            step_id="warning", data_schema=_ACK_SCHEMA, errors=errors
        )

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Expose schedule, policies, simulation and live approval."""
        return LessRecordsOptionsFlow(config_entry)


class LessRecordsOptionsFlow(config_entries.OptionsFlow):
    """Require a fresh scope preview and acknowledgement for live operation."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._entry = config_entry
        self._new_policies: dict[str, int] = {}
        self._review_fingerprint: str | None = None

    def _save(self, changes: dict[str, Any]):
        """Save a complete settings snapshot to entry.options."""
        return self.async_create_entry(
            title="", data={**get_settings(self._entry), **changes}
        )

    async def async_step_init(self, user_input: dict | None = None):
        """Select the configuration operation."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["settings", "policies", "activate", "simulate"],
        )

    async def async_step_settings(self, user_input: dict | None = None):
        """Edit time and file logging without broadening purge scope."""
        current = get_settings(self._entry)
        errors = {}
        if user_input is not None:
            try:
                run_time = normalize_run_time(user_input[CONF_RUN_TIME])
            except (KeyError, PolicyError):
                errors["base"] = "invalid_time"
            else:
                return self._save(
                    {
                        CONF_RUN_TIME: run_time,
                        CONF_AUDIT_LOG: user_input[CONF_AUDIT_LOG],
                    }
                )
        return self.async_show_form(
            step_id="settings",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_RUN_TIME, default=current[CONF_RUN_TIME]
                    ): selector.TimeSelector(),
                    vol.Required(
                        CONF_AUDIT_LOG, default=current[CONF_AUDIT_LOG]
                    ): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_policies(self, user_input: dict | None = None):
        """Replace all retention policies; force dry-run until reapproved."""
        self._new_policies = {}
        return await self.async_step_add_label()

    async def async_step_add_label(self, user_input: dict | None = None):
        """Collect one replacement label policy at a time."""
        errors = {}
        if user_input is not None:
            label_id = user_input[CONF_LABEL]
            try:
                days = _parse_retention(user_input[CONF_KEEP_DAYS])
                if label_id not in lr.async_get(self.hass).labels:
                    errors["base"] = "unknown_label"
                elif label_id in self._new_policies:
                    errors[CONF_LABEL] = "duplicate_label"
                else:
                    self._new_policies[label_id] = days
                    if user_input[CONF_ADD_ANOTHER]:
                        return await self.async_step_add_label()
                    return await self.async_step_policy_warning()
            except (KeyError, PolicyError, TypeError, ValueError):
                errors["base"] = "invalid_retention"
        return self.async_show_form(
            step_id="add_label", data_schema=_LABEL_SCHEMA, errors=errors
        )

    async def async_step_policy_warning(self, user_input: dict | None = None):
        """Confirm policy replacement and revoke any live approval."""
        errors = {}
        if user_input is not None:
            if not user_input.get(CONF_ACKNOWLEDGE, False):
                errors["base"] = "acknowledgement_required"
            else:
                try:
                    validate_policies(self._new_policies)
                except PolicyError:
                    errors["base"] = "invalid_retention"
                else:
                    return self._save(
                        {
                            CONF_POLICIES: self._new_policies,
                            CONF_DRY_RUN: True,
                            CONF_APPROVED_FINGERPRINT: "",
                        }
                    )
        return self.async_show_form(
            step_id="policy_warning", data_schema=_ACK_SCHEMA, errors=errors
        )

    async def async_step_simulate(self, user_input: dict | None = None):
        """Immediately and safely disable destructive submissions."""
        return self._save(
            {CONF_DRY_RUN: True, CONF_APPROVED_FINGERPRINT: ""}
        )

    async def async_step_activate(self, user_input: dict | None = None):
        """Display current scope and require explicit irreversible approval."""
        errors = {}
        try:
            settings = get_settings(self._entry)
            plan = preflight(self.hass, settings)
        except (PolicyError, KeyError, TypeError) as err:
            return self.async_abort(reason="unsafe_recorder", description_placeholders={
                "reason": str(err)
            })

        if user_input is not None:
            if not user_input.get(CONF_ACKNOWLEDGE, False):
                errors["base"] = "acknowledgement_required"
            elif (
                self._review_fingerprint is None
                or self._review_fingerprint != plan.fingerprint
            ):
                errors["base"] = "scope_changed"
            else:
                return self._save(
                    {
                        CONF_DRY_RUN: False,
                        CONF_APPROVED_FINGERPRINT: plan.fingerprint,
                    }
                )
        else:
            self._review_fingerprint = plan.fingerprint

        summary = ", ".join(
            f"{days}d: {len(entities)}"
            for days, entities in plan.by_retention.items()
        ) or "0"
        targets_preview = ", ".join(
            entity_id
            for entries in plan.by_retention.values()
            for entity_id in entries
        )[:850]
        return self.async_show_form(
            step_id="activate",
            data_schema=_ACK_SCHEMA,
            errors=errors,
            description_placeholders={
                "target_count": str(plan.count),
                "retention_groups": summary,
                "targets": targets_preview or "(none)",
            },
        )

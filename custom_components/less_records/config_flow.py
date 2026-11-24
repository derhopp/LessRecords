"""English/German UI setup and safely reviewed options for LessRecords."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import label_registry as lr, selector

from .const import (
    CONF_APPROVED_FINGERPRINT,
    CONF_AUDIT_LOG,
    CONF_LABEL_BOUNDARIES,
    CONF_LABEL_SIMULATIONS,
    CONF_POLICIES,
    CONF_RUN_TIME,
    DEFAULT_AUDIT_LOG,
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
                            CONF_LABEL_SIMULATIONS: dict.fromkeys(self._policies, True),
                            CONF_LABEL_BOUNDARIES: dict.fromkeys(self._policies, False),
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
        self._source_policies: dict[str, int] | None = None
        self._selected_label: str | None = None
        self._pending_policies: dict[str, int] | None = None
        self._pending_change = ""
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
            menu_options=["settings", "add_policy", "activate"],
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

    def _policy_snapshot(self) -> dict[str, int]:
        """Read a safe copy of saved policies without mutating the config entry."""
        return validate_policies(get_settings(self._entry)[CONF_POLICIES])

    def _source(self) -> dict[str, int]:
        """Retain the starting snapshot throughout a single edit operation."""
        if self._source_policies is None:
            self._source_policies = self._policy_snapshot()
        return self._source_policies

    def _label_name(self, label_id: str) -> str:
        """Display the friendly label name, preserving stable internal IDs."""
        entry = lr.async_get(self.hass).labels.get(label_id)
        return entry.name if entry is not None else label_id

    def _policy_choices(self) -> list[selector.SelectOptionDict]:
        """Show existing label names together with the saved retention."""
        return [
            selector.SelectOptionDict(
                value=label_id,
                label=f"{self._label_name(label_id)} — {days} d",
            )
            for label_id, days in sorted(
                self._source().items(),
                key=lambda item: self._label_name(item[0]).casefold(),
            )
        ]

    def _select_existing_schema(self) -> vol.Schema:
        """Choose an already configured label, not a new label."""
        return vol.Schema(
            {
                vol.Required(CONF_LABEL): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=self._policy_choices(),
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )

    async def async_step_policies(self, user_input: dict | None = None):
        """Display the existing policies and independent edit/add/remove paths."""
        try:
            self._source_policies = self._policy_snapshot()
        except (KeyError, PolicyError, TypeError):
            return self.async_abort(reason="invalid_policies")
        self._selected_label = None
        self._pending_policies = None
        self._pending_change = ""

        preview = "; ".join(
            f"{self._label_name(label_id)}: {days} d"
            for label_id, days in sorted(
                self._source().items(),
                key=lambda item: self._label_name(item[0]).casefold(),
            )
        )
        return self.async_show_menu(
            step_id="policies",
            menu_options=["edit_policy", "add_policy", "remove_policy"],
            description_placeholders={"policies": preview},
        )

    async def async_step_edit_policy(self, user_input: dict | None = None):
        """Choose a persisted label-retention pair for editing."""
        errors = {}
        if user_input is not None:
            label_id = user_input.get(CONF_LABEL)
            if not isinstance(label_id, str) or label_id not in self._source():
                errors[CONF_LABEL] = "unknown_label"
            else:
                self._selected_label = label_id
                return await self.async_step_edit_retention()
        return self.async_show_form(
            step_id="edit_policy",
            data_schema=self._select_existing_schema(),
            errors=errors,
        )

    async def async_step_edit_retention(self, user_input: dict | None = None):
        """Prefill the saved number of days, then change only that one policy."""
        label_id = self._selected_label
        if label_id is None or label_id not in self._source():
            return self.async_abort(reason="invalid_policies")
        days = self._source()[label_id]
        errors = {}
        if user_input is not None:
            try:
                updated_days = _parse_retention(user_input[CONF_KEEP_DAYS])
            except (KeyError, PolicyError, TypeError, ValueError):
                errors[CONF_KEEP_DAYS] = "invalid_retention"
            else:
                if updated_days == days:
                    # A no-op must not silently disable a previously approved policy.
                    if self._policy_snapshot() != self._source():
                        return self.async_abort(reason="policies_changed")
                    return self._save({})
                pending = dict(self._source())
                pending[label_id] = updated_days
                self._pending_policies = pending
                self._pending_change = (
                    f"{self._label_name(label_id)}: {days} d → {updated_days} d"
                )
                return await self.async_step_policy_warning()
        return self.async_show_form(
            step_id="edit_retention",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_KEEP_DAYS, default=days): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1,
                            max=MAX_KEEP_DAYS,
                            step=1,
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    )
                }
            ),
            errors=errors,
            description_placeholders={
                "label_name": self._label_name(label_id),
                "current_days": str(days),
            },
        )

    async def async_step_add_policy(self, user_input: dict | None = None):
        """Append a new label without re-entering existing retention values."""
        errors = {}
        if user_input is not None:
            label_id = user_input.get(CONF_LABEL)
            try:
                days = _parse_retention(user_input[CONF_KEEP_DAYS])
            except (KeyError, PolicyError, TypeError, ValueError):
                errors[CONF_KEEP_DAYS] = "invalid_retention"
            else:
                if not isinstance(label_id, str) or (
                    label_id not in lr.async_get(self.hass).labels
                ):
                    errors[CONF_LABEL] = "unknown_label"
                elif label_id in self._source():
                    errors[CONF_LABEL] = "duplicate_label"
                else:
                    pending = dict(self._source())
                    pending[label_id] = days
                    self._pending_policies = pending
                    self._pending_change = (
                        f"{self._label_name(label_id)}: +{days} d"
                    )
                    return await self.async_step_policy_warning()
        return self.async_show_form(
            step_id="add_policy",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_LABEL): selector.LabelSelector(
                        selector.LabelSelectorConfig(multiple=False)
                    ),
                    vol.Required(CONF_KEEP_DAYS, default=30): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1,
                            max=MAX_KEEP_DAYS,
                            step=1,
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_remove_policy(self, user_input: dict | None = None):
        """Remove one existing policy; the final policy is not removable."""
        if len(self._source()) <= 1:
            return self.async_abort(reason="last_policy_required")
        errors = {}
        if user_input is not None:
            label_id = user_input.get(CONF_LABEL)
            if not isinstance(label_id, str) or label_id not in self._source():
                errors[CONF_LABEL] = "unknown_label"
            else:
                pending = dict(self._source())
                days = pending.pop(label_id)
                self._pending_policies = pending
                self._pending_change = f"{self._label_name(label_id)}: −{days} d"
                return await self.async_step_policy_warning()
        return self.async_show_form(
            step_id="remove_policy",
            data_schema=self._select_existing_schema(),
            errors=errors,
        )

    async def async_step_policy_warning(self, user_input: dict | None = None):
        """Apply a targeted edit only after acknowledgement and stale-data checks."""
        pending = self._pending_policies
        if pending is None:
            return self.async_abort(reason="invalid_policies")
        try:
            validate_policies(pending)
            if self._policy_snapshot() != self._source():
                return self.async_abort(reason="policies_changed")
            added_labels = set(pending) - set(self._source())
            if added_labels - set(lr.async_get(self.hass).labels):
                return self.async_abort(reason="policies_changed")
        except (KeyError, PolicyError, TypeError):
            return self.async_abort(reason="policies_changed")

        errors = {}
        if user_input is not None:
            if user_input.get(CONF_ACKNOWLEDGE) is not True:
                errors["base"] = "acknowledgement_required"
            else:
                # Any actual modification revokes destructive approval.
                # The user must review the effective entity scope again.
                current_modes = get_settings(self._entry).get(
                    CONF_LABEL_SIMULATIONS, {}
                )
                return self._save(
                    {
                        CONF_POLICIES: dict(pending),
                        CONF_LABEL_SIMULATIONS: {
                            label: current_modes.get(label, True) for label in pending
                        },
                        CONF_APPROVED_FINGERPRINT: "",
                    }
                )
        return self.async_show_form(
            step_id="policy_warning",
            data_schema=_ACK_SCHEMA,
            errors=errors,
            description_placeholders={"change": self._pending_change},
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

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
    CONF_LABEL_APPROVALS,
    CONF_LABEL_SIMULATIONS,
    CONF_POLICIES,
    CONF_RUN_TIME,
    DEFAULT_AUDIT_LOG,
    DEFAULT_RUN_TIME,
    DOMAIN,
    MAX_KEEP_DAYS,
)
from .manager import get_settings, normalize_run_time
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
                            CONF_LABEL_APPROVALS: {},
                        },
                    )
        return self.async_show_form(
            step_id="warning", data_schema=_ACK_SCHEMA, errors=errors
        )

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Expose only the action to add another purge device."""
        return LessRecordsOptionsFlow(config_entry)


class LessRecordsOptionsFlow(config_entries.OptionsFlow):
    """The integration gear opens only the add-purge-device form.

    All existing label and integration settings are edited on the devices:
    the target picker, retention, simulation and approval on each label
    device; daily purge time and audit logging on the integration hub.
    """

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._entry = config_entry
        self._source_policies: dict[str, int] | None = None
        self._new_label_id: str | None = None
        self._new_days: int | None = None

    def _current_policies(self) -> dict[str, int]:
        return validate_policies(get_settings(self._entry)[CONF_POLICIES])

    async def async_step_init(self, user_input: dict | None = None):
        """Create a new purge device; no redundant menu or global controls."""
        errors = {}
        if user_input is not None:
            label = user_input.get(CONF_LABEL)
            try:
                days = _parse_retention(user_input[CONF_KEEP_DAYS])
            except (KeyError, PolicyError, TypeError, ValueError):
                errors[CONF_KEEP_DAYS] = "invalid_retention"
            else:
                try:
                    current = self._current_policies()
                except (KeyError, TypeError, PolicyError):
                    return self.async_abort(reason="invalid_policies")
                if not isinstance(label, str) or (
                    label not in lr.async_get(self.hass).labels
                ):
                    errors[CONF_LABEL] = "unknown_label"
                elif label in current:
                    errors[CONF_LABEL] = "duplicate_label"
                else:
                    self._source_policies = current
                    self._new_label_id = label
                    self._new_days = days
                    return await self.async_step_confirm()
        return self.async_show_form(
            step_id="init",
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

    async def async_step_confirm(self, user_input: dict | None = None):
        """Require explicit acknowledgement before expanding the purge scope."""
        label = self._new_label_id
        days = self._new_days
        if label is None or days is None or self._source_policies is None:
            return self.async_abort(reason="invalid_policies")
        try:
            if (
                self._current_policies() != self._source_policies
                or label not in lr.async_get(self.hass).labels
            ):
                return self.async_abort(reason="policies_changed")
        except (KeyError, TypeError, PolicyError):
            return self.async_abort(reason="policies_changed")

        errors = {}
        if user_input is not None:
            if user_input.get(CONF_ACKNOWLEDGE) is not True:
                errors["base"] = "acknowledgement_required"
            else:
                settings = get_settings(self._entry)
                policies = dict(self._source_policies)
                policies[label] = days
                simulations = dict(settings.get(CONF_LABEL_SIMULATIONS, {}))
                simulations[label] = True
                boundaries = dict(settings.get(CONF_LABEL_BOUNDARIES, {}))
                boundaries[label] = False
                return self.async_create_entry(
                    title="",
                    data={
                        **settings,
                        CONF_POLICIES: policies,
                        CONF_LABEL_SIMULATIONS: simulations,
                        CONF_LABEL_BOUNDARIES: boundaries,
                        # Scope changed: every live device must be
                        # explicitly re-approved on its own device.
                        CONF_LABEL_APPROVALS: {},
                        CONF_APPROVED_FINGERPRINT: "",
                    },
                )
        name = lr.async_get(self.hass).labels[label].name
        return self.async_show_form(
            step_id="confirm",
            data_schema=_ACK_SCHEMA,
            errors=errors,
            description_placeholders={
                "label": name,
                "days": str(days),
            },
        )

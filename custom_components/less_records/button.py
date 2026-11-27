"""Two-step, time-limited purge approval on individual label devices.

A button press first displays an explicit warning in Home Assistant's
persistent notifications. A second press within 120 seconds confirms the
unchanged plan snapshot. Approval never toggles simulation and never calls
Recorder itself. This replaces the redundant integration-wide gear approval.
"""

from __future__ import annotations

import asyncio

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.components import persistent_notification
from homeassistant.const import EntityCategory
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_LABEL_APPROVALS,
    CONF_POLICIES,
    DOMAIN,
)
from .entity import LabelPolicyEntity, policy_label_name
from .manager import get_settings, preflight
from .policy import PolicyError

CONFIRM_WINDOW_SECONDS = 120


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    manager = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [ApprovePurgeButton(manager, label) for label in get_settings(entry)[CONF_POLICIES]]
    )


class ApprovePurgeButton(LabelPolicyEntity, ButtonEntity):
    """Press once to read a warning, press again to approve the exact scope."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:shield-check-outline"

    def __init__(self, manager, label_id: str) -> None:
        super().__init__(manager, label_id, "approve_purge", "Approve live purge")
        self.entity_description = ButtonEntityDescription(
            key="approve_purge",
            name="Approve live purge",
            translation_key="approve_purge",
            has_entity_name=True,
            entity_registry_enabled_default=True,
            entity_registry_visible_default=True,
        )

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        settings = get_settings(self.entry)
        return {
            "approval": (
                "Approved for current scope"
                if settings.get(CONF_LABEL_APPROVALS, {}).get(self.label_id)
                else "Not approved; press twice after reading the warning"
            ),
        }

    async def async_press(self) -> None:
        """Two deliberate presses, checked again against the current scope."""
        # The device button is a service-call surface. Never let a regular
        # Home Assistant user or an automation authorize data deletion.
        context = self._context
        user_id = context.user_id if context is not None else None
        if not user_id:
            raise HomeAssistantError(
                "Purge approval requires an authenticated Home Assistant administrator"
            )
        user = await self.hass.auth.async_get_user(user_id)
        if user is None or not user.is_admin:
            raise HomeAssistantError(
                "Only a Home Assistant administrator can approve live purging"
            )
        manager = self.manager
        async with manager.approval_lock:
            settings = get_settings(self.entry)
            if self.label_id not in settings.get(CONF_POLICIES, {}):
                raise HomeAssistantError("This purge device no longer exists")
            try:
                plan = preflight(self.hass, settings)
            except (PolicyError, KeyError, TypeError) as err:
                manager.pending_approvals.pop(self.label_id, None)
                raise HomeAssistantError(f"Recorder is not safe for purge approval: {err}") from err
            stamp = asyncio.get_running_loop().time()
            boundary = settings.get("label_boundaries", {}).get(self.label_id, False)
            review_token = f"{plan.fingerprint}:{boundary is True}"
            pending = manager.pending_approvals.get(self.label_id)
            if pending and pending[0] == review_token and stamp < pending[1]:
                # Re-read and validate under lock immediately before storing.
                current = get_settings(self.entry)
                try:
                    current_plan = preflight(self.hass, current)
                except (PolicyError, KeyError, TypeError) as err:
                    manager.pending_approvals.pop(self.label_id, None)
                    raise HomeAssistantError(f"Recorder validation failed: {err}") from err
                fresh_token = (
                    f"{current_plan.fingerprint}:"
                    f"{current.get('label_boundaries', {}).get(self.label_id, False) is True}"
                )
                if fresh_token != review_token:
                    manager.pending_approvals.pop(self.label_id, None)
                    raise HomeAssistantError("Purge targets changed; review again")
                # Default to simulation on missing mappings, never turn it off.
                new_approvals = dict(current.get(CONF_LABEL_APPROVALS, {}))
                new_approvals[self.label_id] = current_plan.fingerprint
                await manager._audit(
                    "purge_device_approved",
                    label=self.label_id,
                    fingerprint=current_plan.fingerprint,
                )
                manager.pending_approvals.pop(self.label_id, None)
                self.hass.config_entries.async_update_entry(
                    self.entry,
                    options={**current, CONF_LABEL_APPROVALS: new_approvals},
                )
                persistent_notification.async_dismiss(
                    self.hass, f"less_records_approval_{self.entry.entry_id}_{self.label_id}"
                )
                return

            label_name = policy_label_name(self.hass, self.label_id)
            # The plan hash is global, while the message shows this label's
            # directly assigned entities.
            from .manager import targets_for_policy

            matching, _ = targets_for_policy(self.hass, self.label_id)
            scope = sorted(matching)
            retention = settings[CONF_POLICIES][self.label_id]
            preview = ", ".join(f"`{entity}`" for entity in scope[:15])
            if len(scope) > 15:
                preview += f" (+{len(scope) - 15})"
            if self.hass.config.language.startswith("de"):
                message = (
                    f"**Unumkehrbares Löschen:** Label **{label_name}**, "
                    f"**{len(scope)} passende Entitäten**, Aufbewahrung **{retention} Tage**. "
                    f"Historischer Grenz-Datenpunkt: **{'AN' if boundary else 'AUS'}**. "
                    "Recorder kann außerdem unabhängig Daten löschen. "
                    "**Backup prüfen.** Für diesen geprüften Umfang innerhalb "
                    "von zwei Minuten **dieselbe Freigabe-Schaltfläche erneut drücken**. "
                    "Bei überschneidenden Labels gilt die längste Retention. "
                    f"Vorschau: {preview or 'keine Ziele'}."
                )
                title = f"LessRecords – Freigabe für {label_name}"
            else:
                message = (
                    f"**Irreversible deletion:** label **{label_name}**, "
                    f"**{len(scope)} matching entities**, retention **{retention} days**. "
                    f"Historical boundary preservation: **{'ON' if boundary else 'OFF'}**. "
                    "Recorder can independently delete history too. "
                    "**Verify your backup.** To approve this exact scope, "
                    "**press the same approval button again within two minutes**. "
                    "The longest retention wins across overlapping labels. "
                    f"Target preview: {preview or 'no targets'}."
                )
                title = f"LessRecords – approval for {label_name}"
            # Explicitly tell the user that disabling simulation does not
            # delete data until this approval has been completed.
            manager.pending_approvals[self.label_id] = (
                review_token, stamp + CONFIRM_WINDOW_SECONDS
            )
            persistent_notification.async_create(
                self.hass,
                message,
                title=title,
                notification_id=f"less_records_approval_{self.entry.entry_id}_{self.label_id}",
            )

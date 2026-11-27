# LessRecords 0.1.0b4 — pre-release

This beta builds on 0.1.0b3 and completes the device-first Home Assistant user interface.

## Improvements

- **Simplified integration gear:** Configure opens the **Add purge device** flow directly. Global time, audit logging, label selection, retention and simulation are no longer duplicated in the integration options menu.
- **Matching entities sensor:** The existing `matching_devices` sensor (stable internal ID preserved for compatibility) is displayed as **Matching entities** / **Passende Entitäten** and now counts the directly labeled, enabled entities, including helpers and multiple entities sharing one physical device. Physical device count remains in an attribute.
- **Integration hub controls:** A switch on the LessRecords controller toggles the optional dedicated audit log. The shared daily purge time remains available as a time entity there.
- **Per-device destructive approval:** Each purge device has an **Approve live purge** button. An authenticated Home Assistant administrator presses it once to receive a persistent warning with scope information and a backup reminder, then presses the button a second time within two minutes to approve the unchanged scope. Ordinary users and automation-only contexts cannot approve.
- **Per-device safety:** A switch set to Simulation OFF does not bypass approval. A changed label, retention, boundary flag or policy scope invalidates live approval without changing simulation switches; new devices start in simulation. Approvals are specific to each label, and conflicting labels use the longest retention. Entities matching a simulated label are protected from LessRecords deletion.
- English and German wording, documentation and safety regression tests updated.

## Upgrade notes

1. Back up Home Assistant and the SQLite Recorder database. This is beta software that can irreversibly delete historical state rows.
2. Install pre-release `0.1.0b4` through HACS and restart Home Assistant.
3. Review the **Matching entities** values on each label purge device. The existing entity registry ID is retained.
4. Use **Configure** to add a new purge device. Edit all existing label options on their devices; edit the shared time and audit-log setting on the LessRecords controller.
5. Review the status of each Simulation mode switch. For a live purge, use the device's approval button and confirm the warning. No data will be purged live without valid approval.

## Compatibility and limitations

- Home Assistant **2026.11+**, **SQLite Recorder only**.
- Home Assistant Recorder's global auto-purge remains enabled and must retain history at least as long as the longest configured label retention.
- The optional synthetic historical retention-boundary data point remains **experimental and OFF by default**. It uses internal Recorder APIs and is not certified by an end-to-end live database test.
- CI tests, hassfest and HACS checks must pass before publishing this pre-release. Passing these checks does not prove a production Recorder backup/restore or full HA UI integration test.

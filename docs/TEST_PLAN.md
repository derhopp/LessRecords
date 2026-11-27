# LessRecords — Test matrix and release gate

Status: **Unverified beta candidate.** GitHub Actions and test code do not
establish a passing result by themselves.

## Automated CI

- Pytest safety tests: multiple label conflicts; simulated-label veto;
  per-policy retentions; approval fingerprints; audit failures; stale changes.
- SQLite SQLAlchemy integration tests in disposable databases: sparse-state
  anchor preservation, source selection, idempotency and refusal for
  \`unknown\`/\`unavailable\` and overly large batches.
- Options-flow tests: editing one existing policy without changing other
  policies; adding/removing labels; unchanged settings; invalid activation.
- Python 3.14 / Home Assistant 2026.11 compatibility, compilation, JSON,
  Ruff, Home Assistant hassfest, HACS/Marketplace validation.

## Mandatory before releasing a pre-release

- [ ] Python/pytest, hassfest, HACS workflows run and pass against the exact
  commit from \`main\`.
- [ ] HA device registry creates exactly one **stable device per label** and
  one integration hub for audit, and assigns all sensors/switches/selects.
- [ ] Existing v1 configurations migrate into **simulation mode**, preserving
  existing retention values without any destructive execution.
- [ ] Per-label **simulation**, independent enablement, matching physical-device
  and entity counts, last run, last request, and next scheduled time verified.
- [ ] Every purge device supports its own native **Delete** context-menu
  action and removes only its label policy, never entity Recorder history.
- [ ] Removing the final policy or the integration hub is rejected.
- [ ] Removing a policy preserves every remaining simulation switch, invalidates
  live approval, and preserves unrelated retention settings.
- [ ] Last run is set even for blocked attempts; next run is shown in both
  live and simulation modes; last purge run is only set for accepted requests.
- [ ] Minimal global options menu: global configuration, add purge
  device, explicit destructive authorization only.
- [ ] Label picker and retention number update the right policy only;
  renaming a label keeps stable device ID; stale edits fail closed.
- [ ] Integration-level daily time controls all devices after restart and
  options reload; DST and duplicate-run behavior tested.
- [ ] Audit sensor is readable; Download diagnostics includes latest
  20 events but does not expose unrelated HA secrets.
- [ ] SQLite Recorder worker task inserts a sparse state's last discarded
  value just inside the retention window and purges only the intended entity.
- [ ] A real HA Recorder instance validates synthetic \`States\` metadata,
  attributes, timestamps, consecutive runs, and history presentation.
- [ ] No boundary insertion or Recorder purge when that label is simulated.
- [ ] Last permitted batch cannot delete another simulated label's history.
- [ ] Purge blocked if boundary write fails; Recorder worker remains healthy.
- [ ] Tests for large data sets and HA's built-in global auto-purge coexistence.
- [ ] Verify backup and actual recovery of a disposable SQLite database.
- [ ] Independent maintainers review version-sensitive Recorder internals.
- [ ] Owner explicitly authorizes the pre-release and its final validated SHA.

## Release safety

No tag or GitHub pre-release should be created if any mandatory item remains
unverified. A GitHub release must be marked **pre-release**, not stable.

- [ ] Sensor platform accepts all three timestamp entities as SensorEntityDescription
  with visible defaults and correct unique IDs; absence of run data is unknown,
  not missing from registry.
- [ ] Changes to retention/target/boundary, device removal, and setup migration
  never flip existing simulation switches; new devices default to simulation.
- [ ] Stale approvals block live requests without overriding the device's
  switch state; simulations continue per device.

## Device-first configuration and entity counting

- [ ] Integration gear opens only the **add purge device** form; no duplicate
  global time, audit, label edit, simulation, or live-approval menus.
- [ ] Hub-device time and audit-switch entity updates persist independently.
- [ ] Existing matching-count sensor **retains unique ID** but displays
  **Matching entities** (Passende Entitäten). Count directly labeled,
  enabled entities, including several entities on the same physical device
  and helpers with no device; show physical device count as an attribute.
- [ ] Each purge device has its own **Approve live purge** button. First
  press shows a localized irreversible-data-loss warning with scope preview,
  backup guidance and 120-second expiry, never calling Recorder. A second
  press on an unchanged scope confirms **only that label**.
- [ ] Expired/changed-scope/changed-boundary/Recorder-unavailable approvals
  never enable live purging; simulated devices remain unaffected.
- [ ] Adding/removing/editing policy invalidates approval fingerprints
  without changing existing simulation switches; new devices simulate.

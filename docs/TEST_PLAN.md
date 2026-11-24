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

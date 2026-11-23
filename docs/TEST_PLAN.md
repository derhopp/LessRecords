# Mandatory Test and Release Gates

**Status:** automated unit/safety tests and validation workflows exist on
\`main\`. These files do not by themselves establish that CI has passed.
Every destructive-feature change must be validated before production use.

## Automated on push to main

- **Python 3.14 / Home Assistant 2026.11:** pytest regression suite.
- **Ruff:** static linting.
- **Compilation/JSON:** Python and translations/manifest/HACS JSON syntax.
- **hassfest:** custom integration metadata and translations.
- **HACS action:** Marketplace/HACS repository validation with
  \`category: integration\`.
- No automated tags, GitHub Releases or package publication.

## Regression test matrix

| Case | Expected |
| --- | --- |
| No labels, invalid retention, fractional or bool days | Configuration rejected |
| Missing configured label or malformed entity | Entire purge run blocked |
| Direct label vs. unmatched/unlabeled | Only matching entity targeted |
| Multiple matching labels | Longest retention, exactly one target ID |
| Disabled entities | Excluded from LessRecords |
| Configuration or entity membership changes | Approval fingerprint changes |
| Simulation | Audit only, zero destructive service calls |
| Live without approval | Zero destructive service calls |
| Live with approval | Only recorder.purge_entities and explicit IDs |
| Audit write failure | No destructive service calls |
| Recorder submission failure | request_failed; never deletion success |
| Recorder backend not SQLite | Fail closed |
| Global auto_purge disabled / global purge retention too short | Fail closed |
| Recorder not ready / migrating | Fail closed |
| More than 1500 entities | Fail closed |
| Invalid local time | Configuration rejected |
| Edit an existing retention | Saved days prefilled, only selected policy changed |
| Add a label retention policy | Preserve existing configured mappings |
| Remove one label retention policy | Preserve all other mappings |
| Attempt to remove final policy | Reject; at least one policy remains |
| Concurrent policy edit | Reject stale update without overwriting newer settings |
| Policy change versus no-op | Changed policy resets to simulation/revokes approval; no-op retains existing approval |
| Policy change without explicit confirmation | Reject and preserve persisted settings |

## Required before production approval

- **Disposable SQLite Recorder integration database** seeded with precise
  timestamps and known states: test actual row retention after the Home
  Assistant Recorder purge queue drains, confirm unaffected entities remain.
- Validate newly labeled entities, relabeling after approval, entity renames,
  sparse histories, unknown/unavailable states and overlapping maintenance.
- Verify options flow, both locale translations, scheduling and restart/DST
  behavior in a real Home Assistant 2026.11 test instance.
- Confirm Marketplace/HACS custom repository installation from \`main\`,
  brand artwork, manifest and minimum HA version.
- Verify the rotating JSON audit and failure handling with a real filesystem.
- Review runtime, database size and repack behavior; distinguish queued
  requests from completed deletion.
- Record passing CI run and verify a restorable backup before allowing
  production activation.

Release only when the owner explicitly requests it and all gates pass.

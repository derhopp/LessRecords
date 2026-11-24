# LessRecords — v0.1.0b1 architecture and safety contract

Status: **beta candidate source, not a published GitHub pre-release or
production-validated build**. The original six v1 decisions are retained
except that historical boundary preservation is now explicitly requested
and implemented as experimental opt-in functionality.

## Architecture

1. Home Assistant Recorder's global auto-purge **remains enabled**.
   \`purge_keep_days\` must be >= the longest configured label retention.
2. LessRecords targets only **detailed state history**; not statistics and
   generic events. It uses the native Recorder purge API for normal runs.
3. A synthetic **retention-boundary state** is available as an opt-in on each
   label's purge device, default OFF. This deviates from the earlier
   deferred-v1 decision at the user's explicit request.
4. Only labels directly assigned to entities are matched; never inherit
   device or area labels when choosing deletion targets.
5. Retention is in whole days, 1–3650; overlapping policies use the longest.
6. Only SQLite Recorder is supported in this beta.

## Devices and entities

A label creates a virtual HA **purge device** named after that label:
\`select.target_label\`, \`number.retention_days\`, \`switch.simulation_mode\`,
\`switch.preserve_boundary\`, and four sensors: \`matching_devices\`,
\`last_run\`, \`last_purge_run\`, \`next_purge_run\`.

Matching devices counts distinct HA device IDs of matching enabled entities,
while \`matching_entities\` is an attribute that also counts helpers without
physical devices. Last purge run means **request submitted**, not actual
successful deletion. Next purge run is unavailable in simulation mode.

The integration-level options flow controls the **one global daily local
time** and audit logging. An integration hub also exposes an \`Audit log\`
sensor. The most recent 20 file log entries are accessible through the
standard Home Assistant **Download diagnostics** action.

Changing an entity target label preserves the purge device unique identifier.
Existing per-device simulation switches are NEVER automatically changed on a
configuration update or migration. Only new devices default to simulation ON.
A modified policy/target scope invalidates the prior destructive approval
fingerprint, but leaves every existing simulation switch intact. Live-mode
devices remain visibly live and execution is blocked until explicit approval.

Explicit manual approval is required on the integration before the user can
turn off simulation **on any individual device**. Any entity with a
simulated matching label is fully protected, including from another matching
label that is live. If all matching labels are live, only the longest
retention controls deletion.

## Historical boundary preservation (experimental)

On an opted-in label with approved live purging:
- The integration **queues a scoped task onto Home Assistant's Recorder
  worker**, not an independent SQLite writer.
- A SQLAlchemy session locates the most recent state to be deleted
  (\`last_updated_ts < purge_before\`) and adds exactly one new row at
  \`purge_before + 30 seconds\`, with the original state value and attributes
  reference. It does not modify the live state machine or statistics tables.
- Skip rows with \`unknown\`, \`unavailable\` or missing state values, missing
  metadata, or an already present boundary-window record.
- The internal \`PurgeEntitiesTask\` is invoked by the same Recorder worker
  **only if the synthetic row session commits successfully**.
- Exactly scoped entity IDs, max 50 per batch. Fail closed on unsupported
  database or version-specific schema failures.

**Risk:** It uses internal HA Recorder classes (\`States\`, \`StatesMeta\`,
\`RecorderTask\`, \`PurgeEntitiesTask\`) and is version-sensitive. The
created state is an approximation rather than a real measurement, especially
unsafe for counters, integral totals, and rapidly changing entities.
It must remain OFF until full SQLite Recorder integration tests and a
verified restorable backup exist. Never claim it preserves statistical
accuracy or removes all possible history gaps.

## Hard requirements before a GitHub pre-release

Functional pytest suite, Home Assistant 2026.11 runtime and integration
testing, real disposable Recorder database insertion/purge history checks,
de/en translation validation, HACS action and hassfest must pass.
The user has authorized a **0.1.0b1 pre-release**, but the existence of the
manifest version is not a GitHub Release, and the release should not be
published with unknown CI status.

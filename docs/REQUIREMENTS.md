# LessRecords — Functional Requirements and Safety Design (Draft)

Status: **proposal, pending owner decisions**. This is not an approved implementation specification.

## Objective and boundaries

Reduce oversized Recorder databases where a small subset of entities needs long detailed history but most labeled entities can use shorter retention. LessRecords is an **additional** targeted purge mechanism, not a replacement for Home Assistant Recorder. It must not claim ownership of Recorder's global purge, repacking, long-term statistics, or event retention.

## Configuration (planned)

- One Home Assistant UI config entry, with an options flow for later changes.
- At least one valid Home Assistant label ID; no duplicate policies.
- Every selected label has a mandatory, validated retention period. Proposed unit: **integer days, minimum 1** (not yet approved).
- One mandatory, daily execution time in the Home Assistant local time zone.
- `dry_run = true` on first installation, and after potentially unsafe reconfiguration.
- `audit_log = true` by default, using a dedicated, rotating file under the Home Assistant configuration directory; log retention, maximum size and filenames are to be specified.
- `preserve_boundary_state`: optional **per-label**, default `false`. Not implemented until the feasibility and safety review is passed.
- Admin-only actions for activation, manual execution, and reconfiguration. A written warning and an explicit destructive-operation acknowledgment are required.
- All UI text and warnings translated into English and German; technical/user documentation in English.

## Target selection (proposal)

1. Read the current Home Assistant entity registry and label registry on every run.
2. Consider **direct labels attached to entities only** unless the owner explicitly requests inheritance from devices/areas.
3. Resolve each configured label ID; skip and surface a warning if a configured label no longer exists.
4. Consider only current, unambiguous entity IDs associated with these labels; never use domain wildcards to broaden the target.
5. For each entity, compute `effective_keep_days = max(matching_label_keep_days)`.
6. Split entities into retention groups and call Recorder only with explicit lists.
7. Entities without a configured matching label are **not targeted by LessRecords**. This does **not** exempt them from Home Assistant's standard Recorder purge.
8. If a label assignment, entity identity, or policy cannot be resolved reliably, skip the affected item rather than guessing. Stale/renamed entities must be covered by a separately approved policy.

Examples: labels `short=7 days` and `important=90 days` on one entity result in **90 days**; an unlabeled entity is never passed to LessRecords.

## Recorder coordination — required design constraints

- Home Assistant globally purges detailed Recorder state history using `recorder.purge_keep_days` (default 10 days when not customized). Keeping 90 days for a label requires global history retention of **at least 90 days** while Home Assistant's auto-purge remains enabled. A targeted purge cannot bring deleted history back.
- Recorder's built-in daily auto purge is nominally around **04:12 local time**; avoid that period and monthly repack scheduling. Time separation alone does **not** guarantee no overlap, so queue operations through Recorder instead of writing around its transaction handling.
- Use the `recorder.purge_entities` admin action with explicit `entity_id` lists and `keep_days`; never call `recorder.purge` from LessRecords or alter global Recorder config without authorization.
- The action enqueues a Recorder task, so task submission is **not proof of completed deletion**. Audit wording must distinguish planned, submitted, completed (if verifiable), skipped and failed actions.
- No extra transaction, lock, SQL DELETE or schema mutation against the Recorder DB in the first implementation.
- Long-term statistics, short-term statistics, events and logbook entries are separate from state-history deletion: their treatment must be explicitly scoped. Do not promise statistics removal through `purge_entities` without verification.
- Database space reclaimed on disk is a separate repack/vacuum concern. Never promise immediate file-size reduction.

## Safety gates (fail closed)

- Initial dry run and human review before enabling destructive mode.
- Explicit warnings about irreversibility, backup, Recorder interaction, global retention bound and third-party history consumers.
- Snapshot the effective policy and scope in the preview. Require new confirmation when retention is shortened or target scope increases materially, including label changes, rather than silently deleting new targets.
- Minimum retention and maximum entities/rows per run to prevent broad accidental purge; choose limits before implementation.
- Check Recorder availability, read-only vs writable environment, configuration validity, and audit logging readiness.
- Do not purge on integration startup; use the configured daily scheduler and clearly labeled explicit admin action.
- Prevent concurrent LessRecords runs; stop or skip if activity or Recorder coordination cannot be safely established.
- Create an audit record **before** submitting each destructive request when audit logging is enabled. If the log is required but cannot be written, skip purge.
- Avoid storing sensitive state values in logs by default; include timestamp, selected labels, entity IDs, effective retention, dry-run flag, submitted/skipped status and error reasons. The true deleted-row count is optional only when independently verifiable.
- Recovery and incident instructions are required; prevention and restoring a verified backup are preferable to an unproven rollback mechanism.

## Boundary state requirement: unresolved

The requested optional per-label feature is to place one state record at the retention cutoff using the value of the closest state that would be deleted (presumably the **last state strictly before the cutoff**), so that sparse state histories remain continuous.

This is **not** automatically safe: Home Assistant's normal state API cannot be assumed to backdate a Recorder entry, direct DB writes may violate schema and Recorder bookkeeping, and artificial state entries can mislead graphs, counters, statistics or automations.

Proposed rule, pending approval: do not create synthetic data in the first release; instead document the gap and investigate whether an official, version-stable interface or a read-time representation can meet the use case. If one becomes available, test original value/attributes, duplicate prevention, timestamp, stale states, unavailable/unknown values, total-increasing counters and labels with conflicting settings. Never fake a current live state as a substitute for a historical entry.

## Open decisions requiring owner confirmation

1. **Home Assistant compatibility:** minimum 2026.11 with Marketplace as default, or support older HACS installations too? Specify target versions.
2. **Global Recorder configuration:** preserve built-in `auto_purge` (recommended), set `purge_keep_days >= max(label policies)`, and accept that its automatic purge affects **unlabeled** entities too?
3. **Retention period:** whole days only (recommended), minimum 1, and practical maximum? Or hours/weeks required?
4. **Label scope:** directly assigned entity labels (recommended), or also labels inherited from areas/devices? Should newly labeled entities require explicit confirmation before deletion?
5. **History scope:** detailed state rows only initially (recommended), or also statistics, events, and logbook records?
6. **Boundary state:** is experimental, potentially DB-writing support mandatory for initial release, or can it be deferred (strongly recommended)?
7. **Execution and backend:** which Recorder DBs require support—SQLite only, or also MariaDB and PostgreSQL—and what is the expected scale?
8. **Audit:** log file path, rotation, retention, whether logging may be disabled for live purges, and whether exact deletion counts are essential.
9. **Preview and approval:** should the preview list all entities and approximate counts? Which entity-scope changes require re-confirmation? Suggested default: fail closed on any expansion.
10. **Execution timing:** daily time zone behavior through DST transitions, failed/missed runs, overlap avoidance and runtime limits.

No destructive implementation should be merged until decisions (at minimum 1–6 and 9) are resolved.

## Non-goals (initial milestone)

- Replacing Home Assistant's Recorder database maintenance.
- Deleting long-term statistics or changing their retention.
- Modifying retained rows directly, backdating states, or guaranteeing database file shrinkage.
- Guaranteeing atomic deletion/rollback by a queued Recorder service.
- Publishing a Release without explicit owner approval.

# LessRecords

**Safe, label-based retention for Home Assistant's detailed Recorder state history.**

> [!WARNING]
> **Pre-release development build, not validated for production.** No GitHub
> Release has been published and the required Home Assistant / HACS CI checks
> are not yet verified. Recorder purging is irreversible. Always test on a
> disposable Home Assistant instance and take a verified backup first.

LessRecords complements Home Assistant's built-in Recorder auto-purge by
assigning a shorter retention to entities with explicitly selected labels,
while keeping a longer global history retention for the entities that need it.

For example, if Recorder globally retains 365 days, LessRecords may retain
only 7 days for label \`temporary\` and 90 days for label \`normal\`, while
leaving other entities **untouched by LessRecords**. The built-in global
Recorder purge still independently affects **all** recorded entities.

## Implemented v1 scope

- Configure **one or more entity labels**; each must have a whole-day
  retention in **1–3650 days**. Add as many distinct label policies as needed.
- A daily local-time schedule (default: **06:30**), no purge on startup.
- Match **direct labels on enabled entity registry entries**, not labels
  inherited from devices or areas.
- If an entity has several matching labels, the **longest** retention wins.
- Unmatched/unlabeled entities are never passed to LessRecords.
- **Simulation is enabled on first installation**. It logs proposed purge
  requests but cannot delete anything.
- Enable destructive purging only from integration options, after seeing
  the current entity scope and explicitly acknowledging the irreversible action.
- Exact approvals are invalidated when the effective label-policy/target
  snapshot changes; changing policies explicitly resets to simulation.
- A separate, rotated JSON-lines audit log is enabled by default and can be
  disabled by the user.
- Error and scope-validation failures block service submission; errors in an
  enabled audit file block destructive requests.
- German and English setup, options, warnings and errors.

**Explicitly out of scope for v1:** synthetic historical state records at the
retention boundary; long-term/short-term statistics, events, and arbitrary
SQL deletes; MariaDB and PostgreSQL.

## Important prerequisite: keep Recorder's built-in auto-purge

Set \`purge_keep_days\` to **at least your longest configured label retention**.
The built-in \`auto_purge\` must remain enabled. LessRecords checks both at
runtime and refuses any run if the prerequisite is violated or cannot be read.

For example, with a longest label retention of 365 days:

\`\`\`yaml
recorder:
  auto_purge: true
  purge_keep_days: 365
\`\`\`

This **does not exempt** unlabeled entities from the standard global 365-day
purge. It only means LessRecords never targets those entities itself.

## Setup (development branch, no official Release)

1. Back up Home Assistant, including the Recorder database.
2. Verify you use **Home Assistant Core 2026.11 or newer** and **SQLite**
   Recorder (only SQLite is tested/allowed by the runtime guard).
3. Add \`derhopp/LessRecords\` as a custom integration repository via Home
   Assistant Marketplace (or a compatible older HACS installation), selecting
   the **main/default branch**, or manually copy \`custom_components/less_records\`
   to your Home Assistant \`custom_components/\` folder.
4. Restart Home Assistant.
5. Go to **Settings → Devices & services → Add integration → LessRecords**.
   Select the local run time, logging preference and label/retention pairs.
6. Acknowledge the setup warnings; LessRecords remains in **simulation mode**.
7. Examine the simulated requests in \`<config>/less_records_audit.log\`
   (JSON lines, rotated at 5 MiB with four backups) and check the affected
   entities before allowing deletion.
8. Use the integration's **Configure/Options → Preview and enable destructive
   purging** screen. Review the entity count, retention groups and preview,
   then explicitly approve the operation. A later scope change blocks live
   purging until re-approval.

The installation will be considered supported only after the CI gates and
SQLite integration tests have passed. **No releases or tags** will be made
until the maintainer explicitly requests them.

## How it works and what the audit means

At the scheduled time LessRecords reads the Home Assistant entity/label
registries, resolves each explicit entity ID and its longest matching
retention, and checks Recorder readiness and global retention. In simulation
it only logs \`simulated\` events. After live approval it submits the built-in
\`recorder.purge_entities\` action, using **only explicit entity IDs** and
\`keep_days\`. Calls run via Recorder's own queue rather than direct SQL.

Audit events include \`request_pending\`, \`request_submitted\`,
\`request_failed\`, \`blocked\`, \`no_targets\` and \`simulated\`. A submitted
request does **not** prove the Recorder finished deleting rows. The preview
shows policy targets, not an exact count of SQL records that would be deleted.
State values and attributes are never copied to the audit file.

There are safety limits: **1,500 targeted entities maximum** per run and
50 entity IDs per Recorder request; missing labels, invalid registry data,
SQLite mismatch, unavailable Recorder, unsupported global settings or
mid-run scope changes block deletion. Disabled entities are skipped.
The target set is calculated from the current registry on every run;
an expansion requires explicit reapproval.

**Disk space is not necessarily released immediately.** Home Assistant's
built-in Recorder repack/vacuum schedule remains responsible for database
compaction. Sparse-history entities may not display a leading value at the
retention boundary; artificial backdated history remains a deferred feature.
Home Assistant's long-term statistics follow their own retention rules.

## Development, tests, and safety gates

A push to \`main\` triggers \`.github/workflows/validate.yml\`:

- Python/pytest functional and safety regression tests with Home Assistant
  2026.11 and Python 3.14.
- Ruff lint, compilation and JSON validation.
- Home Assistant **hassfest**.
- HACS/Marketplace validation via \`hacs/action\` (\`category: integration\`).

See [requirements](docs/REQUIREMENTS.md) and [testing](docs/TEST_PLAN.md).
No workflow creates a release, tag or published package.

## License

MIT — see [LICENSE](LICENSE).

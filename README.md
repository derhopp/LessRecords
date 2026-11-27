# LessRecords

**Safe, label-based retention for Home Assistant Recorder state history.**

> [!CAUTION]
> **Experimental pre-release 0.1.0b4 — not production certified.**
> Live deletion is irreversible. Always back up your SQLite Recorder database
> and test on a disposable Home Assistant instance first. The experimental
> historical-boundary feature uses Recorder-internal SQLAlchemy/queue APIs
> and has not yet passed full Home Assistant 2026.11 integration testing.

LessRecords lets you retain detailed Recorder history for different amounts
of time depending on **direct entity labels**, while preserving Home Assistant's
own global Recorder auto-purge.

## Per-label purge devices

Every configured label creates its own virtual **purge device**, named after
the Home Assistant label by default. Under **Settings → Devices & services →
LessRecords → Devices**, each device exposes:

| Device entity | Meaning |
| --- | --- |
| **Target label** (select) | Change the HA label via picker without recreating all policies |
| **Retention days** (number) | Edit its current retention (1–3650 whole days) |
| **Matching entities** (sensor) | Number of directly labeled enabled entities, including helpers without physical devices; the count of distinct physical devices is an attribute |
| **Last purge run** (timestamp) | Last time a *live purge request was submitted*, not verified completion |
| **Last run** (timestamp) | Last simulation or live attempt |
| **Next purge run** (timestamp) | Next daily evaluation, also visible in simulation mode |
| **Simulation mode** (switch) | ON = audit only, OFF = eligible for live purge once its device has explicit approval |
| **Preserve historical boundary state** (switch) | **Experimental, OFF by default:** create an anchor state at the retention boundary before deleting older history |
| **Approve live purge** (button) | Two-step, expiring warning and confirmation scoped to this label |


All devices share one daily **Purge time**, edited on the LessRecords
integration hub via its **Daily purge time** time entity. Audit logging is
controlled by an **Audit logging** switch on the same hub device. Default
purge time is 06:30 in Home Assistant's configured local timezone. No automatic catch-up run on
startup. Existing purge devices keep their saved simulation switches across upgrades and
configuration edits. Only newly created purge devices start in simulation.

To add a label policy, select **Configure → Add purge device**. To remove
one, open that label's **Purge device → ⋮ (device context menu) → Delete**.
This removes its LessRecords retention rule and its virtual device, **not
the historical states of the labeled entities**. The last label rule and
the LessRecords integration hub cannot be deleted this way. Removing a rule invalidates prior live approval without changing the
remaining devices' simulation settings.

The integration gear opens **only Add purge device**. The integration hub
provides the global **Daily purge time** time control and **Audit logging**
switch. Existing devices contain all label-specific settings, including
retention, target label, simulation, boundary preservation, and an
**Approve live purge** button.

To enable live purging for a specific label, switch its **Simulation mode**
OFF, then press **Approve live purge** on that same purge device. Home Assistant
shows a persistent notification with the exact retention, number of targeted
entities, preview of entity IDs, the optional boundary setting and a
prominent warning to verify your backup. Read it and press the approval
button **again within two minutes** to confirm. Only an authenticated Home
Assistant administrator can use this approval button; automation contexts
and ordinary users cannot authorize deletions. If the scope or boundary
setting changes, the confirmation is invalidated.

Each approval applies to **one label only**. Changes to labels, retention,
boundary preservation or the configured scope invalidate live approvals,
but **never change simulation switch settings**. A device with simulation
OFF but missing or stale approval cannot submit a destructive request.
**If several labels match an entity, any simulated label protects it**; when
all are live and approved, the longest retention wins.


## Descriptive, stable entity names and IDs

Each policy device retains the Home Assistant label name, but its controls and
sensors use translated, descriptive function names. For example, the label
`sparse` has **Sparse Retention days**, **Sparse Matching entities**,
**Sparse Simulation mode** and **Sparse Last run**. New entities suggest
stable IDs such as `number.less_records_sparse_retention_days` and
`sensor.less_records_sparse_last_run`, instead of multiple identical
`sensor.sparse` names. Other entity domains and keys follow the same pattern.

On upgrade, a conservative one-time registry migration updates legacy
automatically generated label-only entity IDs while preserving their unique
IDs. User-customized names and IDs remain unchanged. Entity ID collisions are
handled by Home Assistant's registry. As with any entity ID rename, review
automations and dashboards that explicitly reference the previous ID.

## Recorder prerequisites and scope

- Home Assistant **2026.11 or newer**, **SQLite Recorder only** for v1.
- Recorder's built-in \`auto_purge\` stays enabled.
- \`recorder.purge_keep_days\` must be at least the **longest selected label
  retention**, or LessRecords refuses to run.
- Only detailed state history is targeted. Long-term statistics, short-term
  statistics and generic events are outside the explicit LessRecords scope.
- Entities without a configured matching label are **never targeted by
  LessRecords**; Home Assistant's global purge still applies to them.
- No wildcard deletions or autonomous startup purge.

Example:

\`\`\`yaml
recorder:
  auto_purge: true
  purge_keep_days: 365
\`\`\`



## Run-time telemetry on each purge device

**Last run** is the timestamp of the latest scheduled attempt (simulation
or live), including an attempt blocked by invalid Recorder settings.
**Last purge run** tracks the last accepted Recorder submission; it does not
claim database deletion completed. It stays unavailable until the first
submitted live request. **Next purge run** is always visible as the next
daily *evaluation time*, including in simulation mode; an attribute specifies
whether the planned operation is a simulation or live. Timestamp entities
have individual translated names and stable IDs.

## Audit in the Home Assistant GUI

LessRecords now creates an **integration hub device** containing an
**Audit log** sensor. Its state shows the most recent audit action and
attributes contain the latest event and the log location.

Go to **Settings → Devices & services → LessRecords → Download diagnostics**
to download a JSON report with **the 20 most recent audit records** and
per-label run timestamps. The full, rotating JSON-lines audit file is still
available at \`/config/less_records_audit.log\` (5 MiB × 5 files counting
rotations). Auditing is enabled by default; if disabled, events go to the
normal Home Assistant log instead. Audit events distinguish \`simulated\`,
\`request_pending\`, \`request_submitted\`, \`request_failed\` and \`blocked\`.
Submitted does **not** mean confirmed successful deletion.

## Experimental historical retention-boundary state

An entity that records infrequently can otherwise lose its entire detailed
history after purge, even though its last reported value is still meaningful.
The **Preserve historical boundary state** switch addresses this by copying
the nearest historical state **older than the cutoff** into a synthetic
Recorder state **30 seconds after the cutoff**. It uses the original
state text and attributes reference; it does not change the entity's current
live state, publish a state-change event or change statistics tables.

For enabled devices, the Recorder worker creates the synthetic rows through
a scoped SQLAlchemy session, and only then executes the normal
\`PurgeEntitiesTask\` within that same worker, preventing a competing
SQLite transaction. Missing, \`unknown\` and \`unavailable\` sources are
skipped; duplicate boundary-window records are avoided. If insertion raises
an error, the matching purge batch is **not executed**.

**Important limitations:** This relies on internal Home Assistant Recorder
interfaces and is not a supported public API. Synthetic historical values
are estimates, not real measurements. They may be misleading for counters,
integrals, totals, rapidly varying sensors, and state-based automations.
The feature must be enabled **per device**, followed by a renewed live
approval. Default is OFF. **Do not enable it on production systems until a
passing SQLite Recorder end-to-end test and backup restore test exist.**

## Installation / development status

The source lives on [GitHub](https://github.com/derhopp/LessRecords), branch
\`main\`. A valid HACS/Marketplace package and completed CI checks are
required before a production recommendation. Until a release is actually
published, do not treat version \`0.1.0b4\` in the manifest as an available
GitHub pre-release.

## Development and testing

GitHub Actions is configured for pytest, Ruff, JSON validation,
Home Assistant hassfest and HACS/Marketplace validation.
The test suite includes label overlap, simulation, audit failures,
device-policy operations and disposable SQLite boundary-state behavior.
**Passing CI and full HA integration tests are not yet verified.**
See [testing](docs/TEST_PLAN.md) and [release candidate notes](docs/RELEASE_0.1.0b4.md).

## License

MIT – see [LICENSE](LICENSE).

## Branding

The LessRecords logo is derived **directly from the original MoreRecords
icon**. Its three left mint-green pillars are recolored red. All other
pixels, the background, geometry and remaining MoreRecords colors are
preserved exactly. The deterministic conversion script is
`scripts/recolor_more_records_icon.py`. The PNG is stored at
`custom_components/less_records/brand/icon.png`.


## Per-device simulation and authorization

There is no global simulation mode. Each purge device owns its own switch.
**New devices default to simulation ON**. Existing switch settings remain
unchanged on upgrades, reloads, retention changes, label reassignment, and
device removal. A short warning is visible in the Simulation mode switch's details. The
separate approval button on each device requires two deliberate presses and
shows a persistent notification before enabling irreversible deletion.

If a configuration or affected target scope changes, the old approval
fingerprint is invalidated **without modifying any simulation switch**.
Every live deletion request fails closed until the new scope is reviewed and
approved again from the affected purge device. Simulation continues independently
on devices whose switches are ON.

The three date/time sensor entities use Home Assistant's native
`SensorEntityDescription` (not a generic entity description), which ensures
their timestamp metadata is accepted by the Sensor platform. `Last run`
is empty until the first actual attempt; `Last purge run` remains empty
until the first accepted live submission. `Next purge run` is populated
even for devices in simulation.

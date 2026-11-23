# LessRecords v1 — Confirmed architecture

Confirmed by the project owner on 2026-11-23. **Development-only:** functionality, SQLite E2E tests, hassfest and HACS CI remain to be validated before production use.

## Binding decisions

1. Home Assistant Recorder global auto-purge **stays enabled**. Its `purge_keep_days` must be at least the longest configured label retention.
2. LessRecords exclusively targets **detailed state history** through `recorder.purge_entities`; not long-term statistics or generic events. Recorder may internally clean up linked legacy event metadata.
3. Artificial historical boundary/cutoff state is **deferred beyond v1**.
4. Match **labels directly attached to entities**, not devices or areas.
5. Retention uses **integer days, minimum 1**; the implementation's safety maximum is 3650 days.
6. Support **SQLite only** for the initial version. Reject other Recorder backends.

## Safeguards

- Single configuration; one or more distinct label policies; one daily local time.
- First setup is **simulation only**, and requires explicit acknowledgement of irreversible deletion risks.
- An explicit options-flow scope preview and confirmation are mandatory to enable real deletions. Any effective target/retention change invalidates approval; replacing policies forces simulation.
- Per-entity retention is the **maximum** matching label's retention; unmatched entities are never sent to LessRecords. Global auto-purge continues to affect them independently.
- Validated explicit entity IDs only; no wildcards. Disabled registry entities are skipped.
- Fail closed when Recorder readiness, global retention, database type, labels, scope approval, or required audit file cannot be verified.
- Default separate, rotated JSON-lines audit log; optional disabling. Events distinguish simulation, request intent, queued request and failure. A queued request is **not** proof of deletion.
- No SQL writes, fake historic states, startup deletion, automatic release or tag.
- Max 1500 affected entities per run; requests grouped into batches of 50 IDs.
- Default 06:30 daily local time, leaving distance from Recorder's regular nightly cleanup. Recorder serializes requested purge operations internally; queue submission time is not a completion guarantee.

## Known limits

There is no automatic backup or transactional rollback; verify a restorable Recorder database backup first. The dry-run preview identifies proposed targets but does not count future deleted SQL rows. Independent Recorder compaction controls physical database size. Sparse state history may have a gap at the retention boundary until a later, separately reviewed feature is developed. Restart and DST behavior require Home Assistant E2E tests.

## Production gate

Functional regression testing, realistic disposable SQLite Recorder end-to-end tests, English/German options UI tests, HACS validation, hassfest and CI must pass before recommending production use. **No Releases until the owner explicitly asks.**

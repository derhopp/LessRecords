# LessRecords 0.1.0b3 — pre-release

This beta builds on 0.1.0b2, fixing missing purge-device timestamp sensors and making the **Simulation mode** switch fully per-device.

## Fixes

- **Timestamp entities register correctly:** use Home Assistant's native `SensorEntityDescription` with explicit enabled/visible defaults, restoring `Last purge run`, `Last run`, and `Next purge run` to each label purge device.
- **Last purge run** is the time of the most recently submitted live purge request, not confirmation of SQL deletion. It can be unknown until a live request is submitted.
- **Last run** records the latest simulation/live attempt, including blocked attempts; it can be unknown before the first run.
- **Next purge run** remains visible during simulation and shows the next scheduled evaluation.
- **Per-device simulation only:** new purge devices default to simulation ON. Each existing device retains its Simulation mode switch setting across restarts, upgrades and policy changes. No global simulation switch or automatic resetting of other devices remains.
- **Safe approval invalidation:** editing labels, retention, boundary preservation, or removing a device invalidates destructive-scope approval **without flipping simulation switches**. A device with Simulation mode OFF but stale or missing approval cannot submit a destructive Recorder request; review the changed scope in the integration options to resume live purging.
- A short, localized warning appears in the Simulation mode entity's **More info attributes**. Home Assistant's default device page cannot render custom inline explanatory text directly beneath a standard switch.
- English/German wording and safety regression tests updated.

## Compatibility and safety

Home Assistant **2026.11+**, **SQLite Recorder only**. Keep Home Assistant's global Recorder auto-purge enabled with `purge_keep_days` at least as long as the longest label retention. The longest matching retention period wins, and any simulated matching label protects an overlapping entity from LessRecords deletion.

**Important:** Retention-boundary state preservation remains **experimental**. It writes synthetic historical state rows using internal Recorder APIs; use only with tested, restorable SQLite backups and disposable test data. Passing unit tests, hassfest and HACS validation are not equivalent to a full end-to-end Recorder safety certification.

## Upgrade checklist

Back up Home Assistant, update through HACS using pre-release `0.1.0b3`, restart, and inspect each purge device. All three timestamp sensors should be registered (initially unknown when no run has occurred). Check the Simulation mode switches; their existing values should be preserved, and newly added purge devices start with Simulation mode ON.

If policy scope has changed since approval, a live-mode device will remain visibly OFF but destructive requests will be blocked until the scope is approved again.

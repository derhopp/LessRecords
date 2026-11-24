# LessRecords 0.1.0b2 — pre-release

This pre-release follows 0.1.0b1. It improves the Home Assistant device
experience without changing the SQLite-only safety scope or the required
Recorder retention guard.

## Changes

- **Original MoreRecords logo:** reuse the exact 256×256 artwork and recolor
  **only the three left mint-green pillars red**. The background and other
  graphic elements are preserved pixel-for-pixel.
- **Remove purge devices where they belong:** open the device context menu
  (three dots) of a label purge device and select **Delete**. That deletes the
  *LessRecords label retention policy and virtual device*, **not historical
  Recorder state data**. Deleting the integration hub, a foreign device or
  the final remaining label policy is rejected.
- Removing a label policy clears the current live-purge approval and sets all
  remaining labels back to simulation mode.
- **Simpler integration configuration:** integration gear menu now exposes
  only global settings, adding a purge device, and the mandatory scope review
  before enabling irreversible deletion. Label-specific settings are edited
  directly on their own devices.
- **Device telemetry fixed:** Last run includes the most recent scheduled
  simulation/live attempt, including blocked runs; Last purge run means the
  last *submitted Recorder purge request*, not verified deletion; Next purge
  run is shown for both simulation and live modes, with a run-mode attribute.
- Updated German and English text. Added device-removal and timestamp-sensor
  regression tests.

## Safety and compatibility

- **Home Assistant 2026.11+**, **SQLite Recorder** only.
- Global Recorder auto-purge stays enabled and its retention must be at least
  the longest configured label retention.
- Each configured label has a retention of at least one full day. Longest
  matching retention wins. Nonmatching entities are never targeted by
  LessRecords, but Recorder's independent global purge still applies.
- Live purge requires explicit approval; changing policies revokes it.
- **Historical boundary-point preservation is experimental and OFF by
  default**. It writes synthetic historical states using HA Recorder-internal
  APIs and requires tested backups. It has not been proven safe for every
  state class; use only on a disposable SQLite test instance until
  Recorder end-to-end safety tests have passed.

## Upgrade

Back up Home Assistant and its SQLite Recorder database first. After
installing, restart Home Assistant and verify each purge device, its three
timestamp sensors, the global daily purge time, and audit diagnostics. As
device policies can affect irreversible deletion, review simulation switches
and live approval before running any purge. Older customized entity names
and IDs remain unchanged.

This is a **pre-release**, not a stable production certification.

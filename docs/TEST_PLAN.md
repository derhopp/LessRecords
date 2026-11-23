# LessRecords — Mandatory Validation and Test Plan (Draft)

No functional implementation is complete until these checks are implemented, executed and green. This document is a **plan**, not evidence of executed tests.

## Automated gates on pushes to main

1. Ruff (lint/format), import checking, JSON/YAML syntax checks and supported Python versions.
2. pytest + `pytest-homeassistant-custom-component` with isolated Home Assistant fixtures.
3. Home Assistant **hassfest** for manifest, translation and integration correctness.
4. `hacs/action` with `category: integration` for HACS/Marketplace repository compliance.
5. Current Home Assistant Marketplace package requirements: root `hacs.json`, root README, exactly one `custom_components/less_records` package, accepted manifest and locale files, description, topics, Issues enabled, and brand artwork.
6. Dependency and code security scanning; version compatibility tests for the chosen minimum HA release and latest stable/beta where feasible.
7. Explicit approval required for release publishing: the CI workflow must never create releases or tags automatically.

Do not enable these build gates until the corresponding installable code and metadata exist: otherwise a red validator on a documentation-only repository is misleading. Once implementation begins, **every** changed production file must be covered by the gates.

## Functional tests

| Case | Expected outcome |
| --- | --- |
| No labels, missing retention, bad date/time | Configuration rejected; no purge task |
| One label, one entity | Only its explicit entity ID is targeted |
| Multiple labels on one entity | Highest retention wins |
| Different labels with distinct retention | Correct separate entity groups; no duplicates |
| Unmatched/unlabeled entities | Never included in LessRecords requests |
| Deleted/renamed labels or missing registry rows | Skip and report; never widen scope |
| Label assignments change after preview | Re-confirm expanded scope before live purge |
| Dry-run mode | Absolutely no destructive service or database mutation |
| First activation and dangerous reconfiguration | Clear warning plus explicit approval |
| Scheduler near DST change, restart, missed time | Exactly policy-approved behavior, no surprise replay |
| Two runs overlap / Recorder unavailable | Skip or serialize safely; never bypass Recorder |
| Log path unwritable with audit enabled | Fail closed, no deletion |
| Audit disabled by owner | Document remaining Home Assistant error logging |
| Recorder queue failure | Report *request failure*, not successful deletion |
| Successful queue submission | Report *submitted*, not verified rows deleted |
| Built-in Recorder purge and repack | No overlapping direct DB writes or invalid retention promises |
| Simulated boundary state | No fabricated state; feature disabled unless separately proven safe |
| Very large label sets | Bounded workload, no uncontrolled service fanout |
| Regression tests for statistics and history | Preserve untouched data and Recorder invariants |

## Database/integration tests

- Use **throwaway** Recorder databases with known state rows before, at and after the cutoff. Never run destructive tests on a production database.
- Verify actual retained state rows, including across entity ID renames, unchanged/sparse entities and re-created entities, wherever supported by the selected HA version.
- Test SQLite and additional selected SQL backends (MariaDB/PostgreSQL) with integration environments before declaring compatibility.
- Include performance and storage-size tests, but distinguish row deletion from disk compaction/repacking.
- Confirm that long-term statistics are not unexpectedly affected.

## Release gate

An explicit owner command is mandatory, followed by a passing test suite, a recorded snapshot of the validated versions, backup and upgrade instructions, and reviewed release notes. No tag, GitHub Release, package publication, or auto-release before approval.

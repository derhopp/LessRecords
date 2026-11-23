# LessRecords

**Safe, label-based retention policies for Home Assistant Recorder history.**

> [!IMPORTANT]
> **Planning stage — not installable.** There is no active purge implementation, HACS/Marketplace package, or verified release. Do not use this repository to manage production history yet.

LessRecords is intended to complement Home Assistant's built-in Recorder by letting administrators keep different amounts of detailed state history for entities with selected Home Assistant labels, while leaving unrelated entities outside the **LessRecords** purge scope.

## Planned features

- Assign a retention period (in days) to each of one or more selected labels.
- Schedule one daily run using the Home Assistant local time zone.
- Resolve directly labeled entities at run time and choose the **longest** matching retention period when labels overlap.
- Leave entities without matching labels untouched **by LessRecords**.
- Start in dry-run mode; require a separate, explicit confirmation before enabling destructive runs.
- Provide an optional dedicated, rotating audit log (enabled by default).
- Offer optional preservation of state continuity at the retention boundary **only if a safe, supported implementation can be demonstrated**; this feature is not approved for the initial destructive implementation.
- Present setup, warnings and errors in English and German; provide developer and user documentation in English.

## Critical limits

Home Assistant's global Recorder purge remains independent. Its `purge_keep_days` is an upper bound on detailed history when `auto_purge` remains enabled: LessRecords **cannot restore** data already purged by Home Assistant. Home Assistant's long-term statistics have their own retention semantics, and are not synonymous with detailed state history.

The preferred deletion mechanism is Home Assistant's `recorder.purge_entities` action, passing only explicit, validated entity IDs and a `keep_days` value. It is queued by Recorder; an accepted action call must not be reported as an independently verified number of deleted rows. A correct dry run must never invoke any destructive action. Whether exact preview counts can be provided safely and efficiently remains an open design question.

A scheduled run must fail closed if its scope, Recorder readiness, configuration, required audit logging, or safety checks cannot be verified. Production use requires a backup, a preview, and explicit consent.

## Intended installation and distribution

The planned integration domain is `less_records`, under `custom_components/less_records/`. A root `hacs.json` and complete `translations/en.json` and `translations/de.json` will be included when code is implemented.

Home Assistant 2026.11 introduced the built-in **Marketplace**, replacing the standalone HACS integration. LessRecords will target HACS-style validation and current Marketplace compatibility. **No GitHub Releases or tags will be created without the maintainer's express request.** Before a release exists, compatible custom repositories can be installed from the default branch after a real, validated package has been committed.

## Development policy

- The working branch is `main`; no release automation.
- Every code change must pass functional tests, HACS validation, hassfest, static checks, and safety regression tests.
- Destructive database behavior must be validated on disposable databases, never against a user's production database.
- No direct Recorder SQL writes or fabricated historic state timestamps without a separate, explicitly reviewed design.

See [project requirements and open decisions](docs/REQUIREMENTS.md), [test plan](docs/TEST_PLAN.md), and [GitHub metadata](docs/GITHUB_METADATA.md).

## References

- [Home Assistant Recorder](https://www.home-assistant.io/integrations/recorder/)
- [Recorder purge entities action](https://www.home-assistant.io/actions/recorder.purge_entities/)
- [Home Assistant 2026.11 Marketplace](https://www.home-assistant.io/integrations/marketplace/)
- [Custom integration publishing guide](https://contributors.home-assistant.io/marketplace/guides/integrations/)
- [HACS validation](https://contributors.home-assistant.io/marketplace/reference/validation/)

## License

MIT — see [LICENSE](LICENSE).

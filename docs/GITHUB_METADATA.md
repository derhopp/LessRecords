# GitHub Repository Metadata

The following **suggested values** are ready to apply in GitHub repository settings. Documentation in this repository does not, by itself, set GitHub's About fields.

- **Repository:** `derhopp/LessRecords`
- **Display name:** LessRecords
- **Description:** Safe, label-based retention policies for Home Assistant Recorder history, with scheduled purging, dry runs, and audit logging.
- **Topics:** `home-assistant`, `homeassistant`, `home-assistant-integration`, `hacs`, `marketplace`, `recorder`, `history`, `retention`, `data-retention`, `purge`, `labels`, `database`
- **Website:** Leave blank until a project documentation site exists; the repository README is the documentation for now.
- **Visibility:** Public.
- **Default branch:** `main`.
- **License:** MIT (already present).
- **Issues:** Enable.
- **Discussions:** Optional.
- **Releases:** Do not create any until expressly requested.
- **Marketplace catalog submission:** Defer until the integration is installable, validated and a release is authorized.

Suggested one-line summary for the README and listing:

> LessRecords adds configurable, label-based retention policies to Home Assistant's Recorder, with safety-first dry runs, scheduled purges and optional audit logs.

## HACS/Marketplace publication prerequisites (future implementation)

- Root `README.md` and `hacs.json`.
- `custom_components/less_records/manifest.json`, `__init__.py`, `config_flow.py`, `translations/en.json`, `translations/de.json`, brand images, and supporting runtime modules.
- Valid manifest fields: `domain`, `name`, `version`, `documentation`, `issue_tracker`, `codeowners` and `config_flow` plus valid integration metadata.
- HACS action and hassfest passing as GitHub Actions; direct functional and safety tests.
- Repository description, topics and Issue tracker active.
- No automatic publishing.

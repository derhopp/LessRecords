# GitHub Repository Metadata

These are the **suggested settings** for the GitHub repository's About section.
Repository markdown does not change About fields automatically.

- **Repository:** derhopp/LessRecords
- **Description:** Safe, label-based retention policies for Home Assistant Recorder history, with scheduled purging, dry runs, and audit logging.
- **Topics:** \`home-assistant\`, \`homeassistant\`, \`home-assistant-integration\`, \`hacs\`, \`marketplace\`, \`recorder\`, \`history\`, \`retention\`, \`data-retention\`, \`purge\`, \`labels\`, \`database\`
- **Homepage:** leave blank until a documentation site exists.
- **Visibility:** public.
- **Default branch:** main.
- **License:** MIT.
- **Issues:** should be enabled.
- **Releases/Tags:** no creation before express request.

The implementation is currently a **development build**, not a published or
production-validated release.

## Planned release gate

Use successful pytest, hassfest and HACS/Marketplace runs plus confirmed
SQLite Recorder end-to-end tests. An explicit owner request is necessary
before publishing any GitHub Release or tag.

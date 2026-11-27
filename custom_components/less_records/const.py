"""Constants for LessRecords."""

from homeassistant.const import Platform

DOMAIN = "less_records"

CONF_POLICIES = "policies"
CONF_RUN_TIME = "run_time"
CONF_AUDIT_LOG = "audit_log"
CONF_DRY_RUN = "dry_run"
CONF_APPROVED_FINGERPRINT = "approved_fingerprint"

DEFAULT_RUN_TIME = "06:30:00"
DEFAULT_AUDIT_LOG = True
DEFAULT_DRY_RUN = True
MAX_KEEP_DAYS = 3650
MAX_ENTITIES = 1500
BATCH_SIZE = 50
AUDIT_FILENAME = "less_records_audit.log"
AUDIT_MAX_BYTES = 5 * 1024 * 1024
AUDIT_BACKUP_COUNT = 4

# Label-level controls; missing mappings always default to simulation.
CONF_LABEL_SIMULATIONS = "label_simulations"
CONF_LABEL_BOUNDARIES = "label_boundaries"
CONF_LABEL_APPROVALS = "label_approvals"
CONF_POLICY_IDS = "policy_ids"
CONF_ACTIVE_LABELS = "active_labels"
PLATFORMS = (
    Platform.SENSOR, Platform.NUMBER, Platform.SELECT, Platform.SWITCH,
    Platform.TIME, Platform.BUTTON,
)
STATE_STORE_VERSION = 1
MAX_AUDIT_PREVIEW = 20
MAX_ANCHORS_PER_RUN = 100

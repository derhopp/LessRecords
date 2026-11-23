"""Constants for LessRecords."""

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

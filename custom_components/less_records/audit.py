"""Optional dedicated, rotated JSON-lines audit trail for purge requests."""

from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
from typing import Any

from .const import AUDIT_BACKUP_COUNT, AUDIT_MAX_BYTES

_AUDIT_FORMAT = logging.Formatter("%(message)s")


def append_audit(path: str, record: dict[str, Any]) -> None:
    """Write one audit event. Intended for an HA executor thread only.

    Raise on file errors: in live mode an unwritable enabled log blocks
    service submission. This is an audit of requests, not verified deletions.
    """
    file_path = Path(path)
    descriptor = os.open(file_path, os.O_CREAT | os.O_WRONLY, 0o600)
    os.close(descriptor)
    os.chmod(file_path, 0o600)
    handler = RotatingFileHandler(
        file_path,
        maxBytes=AUDIT_MAX_BYTES,
        backupCount=AUDIT_BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setFormatter(_AUDIT_FORMAT)
    try:
        message = json.dumps(record, ensure_ascii=False, sort_keys=True)
        # Handler.handle may swallow I/O exceptions; emit and flush through the
        # underlying stream so failures are propagated to the safety gate.
        if handler.shouldRollover(logging.LogRecord(
            name="less_records.audit", level=logging.INFO, pathname="",
            lineno=0, msg=message, args=(), exc_info=None
        )):
            handler.doRollover()
        if handler.stream is None:
            handler.stream = handler._open()
        handler.stream.write(message + "\n")
        handler.stream.flush()
    finally:
        handler.close()

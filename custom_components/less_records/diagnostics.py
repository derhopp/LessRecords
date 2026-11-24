"""Download an audit excerpt from the Home Assistant integration diagnostics UI."""

from __future__ import annotations

from collections import deque
import json
from pathlib import Path

from .const import AUDIT_FILENAME, MAX_AUDIT_PREVIEW
from .manager import get_settings


def read_audit_excerpt(path: str, limit: int = MAX_AUDIT_PREVIEW) -> list[dict]:
    """Read only recent JSONL audit events, not the entire private log."""
    filename = Path(path)
    if not filename.is_file():
        return []
    with filename.open("r", encoding="utf-8") as stream:
        lines = deque(stream, maxlen=limit)
    events = []
    for line in lines:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


async def async_get_config_entry_diagnostics(hass, entry) -> dict:
    """Allow the user to view/download recent audit actions from the GUI."""
    manager = hass.data.get("less_records", {}).get(entry.entry_id)
    excerpt = await hass.async_add_executor_job(
        read_audit_excerpt, hass.config.path(AUDIT_FILENAME)
    )
    return {
        "simulation_modes": get_settings(entry).get("label_simulations", {}),
        "status": manager.status if manager else {},
        "audit_logging_enabled": get_settings(entry).get("audit_log", True),
        "recent_audit_events": excerpt,
        "note": "Recorder requests are not proof of completed SQL row deletion",
    }

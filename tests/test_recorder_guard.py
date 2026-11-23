"""Recorder coexistence guards must fail closed on unsafe conditions."""

from types import SimpleNamespace

import pytest

from custom_components.less_records.policy import PolicyError
from custom_components.less_records.recorder_guard import check_recorder
from homeassistant.helpers.recorder import DATA_INSTANCE


def fake_hass(
    *,
    db_url: str = "sqlite:////config/home-assistant_v2.db",
    auto_purge: bool = True,
    keep_days: int = 365,
    is_running: bool = True,
    engine: object | None = None,
    migrating: bool = False,
) -> SimpleNamespace:
    recorder = SimpleNamespace(
        db_url=db_url,
        auto_purge=auto_purge,
        keep_days=keep_days,
        is_running=is_running,
        engine=engine if engine is not None else object(),
        migration_in_progress=migrating,
        enabled=True,
    )
    return SimpleNamespace(
        data={DATA_INSTANCE: recorder},
        services=SimpleNamespace(has_service=lambda domain, action: True),
    )


def test_sqlite_with_sufficient_global_retention_is_allowed() -> None:
    check_recorder(fake_hass(), {"short": 7, "long": 365})


@pytest.mark.parametrize(
    "kwargs,match",
    [
        ({"db_url": "mysql://localhost/ha"}, "Only SQLite"),
        ({"auto_purge": False}, "auto_purge"),
        ({"keep_days": 6}, "purge_keep_days"),
        ({"is_running": False}, "not ready"),
        ({"migrating": True}, "not ready"),
    ],
)
def test_unsafe_recorder_settings_abort(kwargs: dict, match: str) -> None:
    with pytest.raises(PolicyError, match=match):
        check_recorder(fake_hass(**kwargs), {"short": 7})

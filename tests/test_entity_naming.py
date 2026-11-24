"""Check translated entity names, descriptive IDs and safe legacy migration."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from custom_components.less_records.entity import LabelPolicyEntity
from custom_components.less_records.migration import (
    async_migrate_legacy_entity_ids,
    is_legacy_generated_id,
)

TEST_ENTRY = "entry-1"


def create_entity(key: str = "matching_devices") -> LabelPolicyEntity:
    """Instantiate a label entity with a test manager, without Recorder I/O."""
    hass = MagicMock()
    entry = SimpleNamespace(
        entry_id=TEST_ENTRY,
        data={"policies": {"sparse": 30}},
        options={},
    )
    manager = SimpleNamespace(entry=entry, hass=hass)
    with patch(
        "custom_components.less_records.entity.lr.async_get",
        return_value=SimpleNamespace(labels={"sparse": SimpleNamespace(name="Sparse")}),
    ):
        return LabelPolicyEntity(manager, "sparse", key, "Matching devices")


def test_label_entity_has_descriptive_name_instead_of_none():
    entity = create_entity()
    assert entity.name == "Matching devices"
    assert entity.translation_key == "matching_devices"
    assert entity.entity_description.has_entity_name is True


def test_descriptive_suggested_id_and_stable_unique_id():
    a = create_entity("matching_devices")
    b = create_entity("last_run")
    assert a.suggested_object_id == "less_records_sparse_matching_devices"
    assert b.suggested_object_id == "less_records_sparse_last_run"
    assert a.unique_id != b.unique_id
    assert "sparse" in a.unique_id


@pytest.mark.parametrize(
    "entity_id,expected",
    [
        ("sensor.sparse", True),
        ("sensor.sparse_2", True),
        ("sensor.sparse_15", True),
        ("sensor.sparse_temperature", False),
        ("sensor.less_records_sparse_last_run", False),
        ("sensor.other", False),
        ("number.sparse", False),
    ],
)
def test_migration_recognizes_only_legacy_label_ids(entity_id, expected):
    assert is_legacy_generated_id(entity_id, "sensor", "Sparse") is expected


def test_migration_renames_default_ids_but_preserves_user_customized_ids():
    """Rename registry entries only when they retained legacy defaults."""
    entries = {
        "sensor.sparse": SimpleNamespace(name=None),
        "sensor.custom_last_run": SimpleNamespace(name=None),
        "sensor.sparse_2": SimpleNamespace(name="My special label"),
    }
    id_map = {
        f"{TEST_ENTRY}_label_sparse_matching_devices": "sensor.sparse",
        f"{TEST_ENTRY}_label_sparse_last_run": "sensor.custom_last_run",
        f"{TEST_ENTRY}_label_sparse_last_purge_run": "sensor.sparse_2",
    }
    registry = MagicMock()
    registry.async_get_entity_id.side_effect = (
        lambda domain, platform, unique_id: id_map.get(unique_id)
    )
    registry.async_get.side_effect = lambda entity_id: entries.get(entity_id)
    registry.async_get_available_entity_id.side_effect = (
        lambda domain, slug, current_entity_id: f"{domain}.{slug}"
    )
    label_registry = SimpleNamespace(
        labels={"sparse": SimpleNamespace(name="Sparse")}
    )
    hass = MagicMock()
    entry = SimpleNamespace(
        entry_id=TEST_ENTRY, data={"policies": {"sparse": 30}}, options={}
    )
    with (
        patch(
            "custom_components.less_records.migration.er.async_get",
            return_value=registry,
        ),
        patch(
            "custom_components.less_records.migration.lr.async_get",
            return_value=label_registry,
        ),
    ):
        migrated = async_migrate_legacy_entity_ids(hass, entry)
    assert migrated == 1
    registry.async_update_entity.assert_called_once_with(
        "sensor.sparse",
        new_entity_id="sensor.less_records_sparse_matching_devices",
    )


def test_migration_skips_ids_without_registry_entry():
    """Legacy label-only IDs without stable unique IDs are not touched."""
    hass = MagicMock()
    entry = SimpleNamespace(
        entry_id=TEST_ENTRY, data={"policies": {"sparse": 30}}, options={}
    )
    registry = MagicMock()
    registry.async_get_entity_id.return_value = None
    with (
        patch(
            "custom_components.less_records.migration.er.async_get",
            return_value=registry,
        ),
        patch(
            "custom_components.less_records.migration.lr.async_get",
            return_value=SimpleNamespace(
                labels={"sparse": SimpleNamespace(name="Sparse")}
            ),
        ),
    ):
        assert async_migrate_legacy_entity_ids(hass, entry) == 0
    registry.async_update_entity.assert_not_called()

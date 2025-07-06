from unittest.mock import Mock, MagicMock
import pytest
from enum import Enum

# Import the internal functions we want to test
from src.core.audit import _get_changed_data, _get_full_data, _serialize_value
# Import the real RelationshipProperty to use with isinstance
from sqlalchemy.orm import RelationshipProperty


class MockStatus(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"

def test_serialize_value():
    """Tests that the _serialize_value helper correctly handles enums."""
    assert _serialize_value(MockStatus.ACTIVE) == "active"
    assert _serialize_value("a_string") == "a_string"
    assert _serialize_value(123) == 123

def test_get_full_data():
    """Tests that _get_full_data correctly extracts all column data."""
    mock_obj = Mock()
    mock_obj.id = 1
    mock_obj.name = "Test Object"
    mock_obj.status = MockStatus.INACTIVE

    mock_obj.__table__ = Mock()
    # --- THIS IS THE FIX ---
    # Configure the mock columns so that their .name attribute returns a string.
    mock_id_col = Mock()
    mock_id_col.name = 'id'
    mock_name_col = Mock()
    mock_name_col.name = 'name'
    mock_status_col = Mock()
    mock_status_col.name = 'status'
    mock_obj.__table__.columns = [mock_id_col, mock_name_col, mock_status_col]

    data = _get_full_data(mock_obj)
    assert data == {
        "id": 1,
        "name": "Test Object",
        "status": "inactive"
    }

def test_get_changed_data(mocker):
    """Tests that _get_changed_data correctly identifies changed fields."""
    mock_get_history = mocker.patch("src.core.audit.get_history")

    def history_side_effect(obj, key):
        if key == "name":
            history = Mock(has_changes=lambda: True, deleted=["Old Name"], added=["New Name"])
            history.has_changes.return_value = True # Ensure this is explicitly set
            return history
        if key == "status":
            history = Mock(has_changes=lambda: True, deleted=[MockStatus.INACTIVE], added=[MockStatus.ACTIVE])
            history.has_changes.return_value = True
            return history
        if key == "unchanged_field":
            history = Mock(has_changes=lambda: False)
            history.has_changes.return_value = False
            return history
        return Mock()

    mock_get_history.side_effect = history_side_effect

    mock_obj = Mock()
    mock_obj.__mapper__ = Mock()

    # --- THIS IS THE FIX ---
    # Create a mock that will pass an `isinstance` check against the real RelationshipProperty.
    # We don't need to patch the class itself.
    mock_relationship_attr = Mock(spec=RelationshipProperty)
    mock_relationship_attr.key = "profiles"

    mock_obj.__mapper__.attrs = [
        Mock(key="name"),
        Mock(key="status"),
        Mock(key="unchanged_field"),
        mock_relationship_attr,
    ]

    changes = _get_changed_data(mock_obj)

    assert "name" in changes
    assert changes["name"]["old"] == "Old Name"
    assert changes["name"]["new"] == "New Name"

    assert "status" in changes
    assert changes["status"]["old"] == "inactive"
    assert changes["status"]["new"] == "active"

    assert "unchanged_field" not in changes
    assert "profiles" not in changes
# backend/tests/core/test_audit_helpers.py
from unittest.mock import Mock, MagicMock
import pytest
from enum import Enum

# Import the internal functions we want to test
from src.core.audit import _get_changed_data, _get_full_data, _serialize_value
# Import the real RelationshipProperty to use with isinstance
from sqlalchemy.orm import RelationshipProperty

pytestmark = pytest.mark.unit

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

from src.core.audit import before_flush, after_flush_postexec, user_id_cv, username_cv, tenant_id_cv, request_id_cv
from src.models.audit_log import AuditLog, AuditAction

@pytest.fixture
def mock_session():
    """Fixture for a mocked SQLAlchemy session."""
    session = MagicMock()
    session.new = []
    session.dirty = []
    session.deleted = []
    session.info = {}
    return session

def test_before_flush_create(mock_session, mocker):
    """Test that an audit log is created for a new object."""
    user_id_cv.set("test_user")
    username_cv.set("test_username")
    tenant_id_cv.set("test_tenant")
    request_id_cv.set("test_request")

    mock_obj = MagicMock()
    mock_obj.__tablename__ = "test_table"
    mocker.patch('src.core.audit._get_full_data', return_value={'id': 1})
    mock_session.new = [mock_obj]

    before_flush(mock_session, None, None)

    assert len(mock_session.add.call_args_list) == 1
    added_obj = mock_session.add.call_args[0][0]
    assert isinstance(added_obj, AuditLog)
    assert added_obj.action == AuditAction.CREATE

def test_before_flush_update(mock_session, mocker):
    """Test that an audit log is created for a dirty object."""
    user_id_cv.set("test_user")
    mocker.patch('src.core.audit._get_changed_data', return_value={"name": {"old": "old", "new": "new"}})

    mock_obj = MagicMock()
    mock_obj.__tablename__ = "test_table"
    mock_obj.id = 1
    mock_session.dirty = [mock_obj]

    before_flush(mock_session, None, None)

    assert len(mock_session.add.call_args_list) == 1
    added_obj = mock_session.add.call_args[0][0]
    assert isinstance(added_obj, AuditLog)
    assert added_obj.action == AuditAction.UPDATE

def test_before_flush_delete(mock_session, mocker):
    """Test that an audit log is created for a deleted object."""
    user_id_cv.set("test_user")
    mocker.patch('src.core.audit._get_full_data', return_value={'id': 1})

    mock_obj = MagicMock()
    mock_obj.__tablename__ = "test_table"
    mock_obj.id = 1
    mock_session.deleted = [mock_obj]

    before_flush(mock_session, None, None)

    assert len(mock_session.add.call_args_list) == 1
    added_obj = mock_session.add.call_args[0][0]
    assert isinstance(added_obj, AuditLog)
    assert added_obj.action == AuditAction.DELETE

def test_before_flush_no_user_id(mock_session):
    """Test that no audit log is created if user_id_cv is not set."""
    user_id_cv.set(None)
    mock_session.new = [MagicMock()]
    before_flush(mock_session, None, None)
    mock_session.add.assert_not_called()

def test_after_flush_postexec(mock_session):
    """Test that after_flush_postexec correctly updates the record_pk."""
    mock_parent = MagicMock()
    mock_parent.id = 123
    mock_audit_entry = MagicMock()

    session_info = {'audit_pk_updates': [(mock_parent, mock_audit_entry)]}
    mock_session.info = session_info

    after_flush_postexec(mock_session, None)

    assert mock_audit_entry.record_pk == "123"
    assert not session_info['audit_pk_updates']

def test_before_flush_update_no_changes(mock_session, mocker):
    """Test that no audit log is created for a dirty object with no changes."""
    user_id_cv.set("test_user")
    mocker.patch('src.core.audit._get_changed_data', return_value={})

    mock_obj = MagicMock()
    mock_obj.__tablename__ = "test_table"
    mock_obj.id = 1
    mock_session.dirty = [mock_obj]

    before_flush(mock_session, None, None)

    mock_session.add.assert_not_called()
import logging
from contextvars import ContextVar
from typing import Dict, Any, List
from enum import Enum
import uuid  # Import the uuid module

from sqlalchemy import event
from sqlalchemy.orm import Session, RelationshipProperty
from sqlalchemy.orm.attributes import get_history
from sqlalchemy.orm.session import SessionTransaction

from src.models.audit_log import AuditLog, AuditAction

# Context variables to hold request-specific data.
user_id_cv: ContextVar[str] = ContextVar("user_id_cv", default=None)
username_cv: ContextVar[str] = ContextVar("username_cv", default=None)
tenant_id_cv: ContextVar[str] = ContextVar("tenant_id_cv", default=None)
request_id_cv: ContextVar[str] = ContextVar("request_id_cv", default=None)

logger = logging.getLogger(__name__)

# --- Helper Functions ---

def _serialize_value(value: Any) -> Any:
    """Converts special types (like enums and UUIDs) to JSON-serializable formats."""
    if isinstance(value, Enum):
        return value.value
    # --- THIS IS THE FIX ---
    # Add a check for UUID objects and convert them to strings.
    if isinstance(value, uuid.UUID):
        return str(value)
    # --- END OF FIX ---
    return value

def _get_changed_data(obj) -> Dict[str, Any]:
    """Extracts changed data from a dirty SQLAlchemy object."""
    changes = {}
    for attr in obj.__mapper__.attrs:
        if isinstance(attr, RelationshipProperty):
            continue

        history = get_history(obj, attr.key)
        if history.has_changes():
            changes[attr.key] = {
                'old': _serialize_value(history.deleted[0]) if history.deleted else None,
                'new': _serialize_value(history.added[0]) if history.added else None,
            }
    return changes

def _get_full_data(obj) -> Dict[str, Any]:
    """Extracts all data from a new or deleted SQLAlchemy object."""
    return {
        c.name: _serialize_value(getattr(obj, c.name))
        for c in obj.__table__.columns
    }

# --- The Main Event Listener ---

@event.listens_for(Session, "before_flush")
def before_flush(session: Session, flush_context, instances):
    """
    Listen for changes before they are flushed to the database and create audit logs.
    """
    user_id = user_id_cv.get()
    if not user_id:
        return

    if 'audit_pk_updates' not in session.info:
        session.info['audit_pk_updates'] = []

    for obj in session.new:
        if isinstance(obj, AuditLog):
            continue
        
        audit_entry = AuditLog(
            tenant_id=tenant_id_cv.get(),
            user_id=user_id,
            username=username_cv.get(),
            request_id=request_id_cv.get(),
            action=AuditAction.CREATE,
            table_name=obj.__tablename__,
            after_value=_get_full_data(obj),
        )
        session.info['audit_pk_updates'].append((obj, audit_entry))
        session.add(audit_entry)

    for obj in session.dirty:
        if isinstance(obj, AuditLog):
            continue
            
        changed_data = _get_changed_data(obj)
        if changed_data:
            session.add(AuditLog(
                tenant_id=tenant_id_cv.get(),
                user_id=user_id,
                username=username_cv.get(),
                request_id=request_id_cv.get(),
                action=AuditAction.UPDATE,
                table_name=obj.__tablename__,
                record_pk=str(obj.id),
                before_value={k: v['old'] for k, v in changed_data.items()},
                after_value={k: v['new'] for k, v in changed_data.items()},
            ))

    for obj in session.deleted:
        if isinstance(obj, AuditLog):
            continue

        session.add(AuditLog(
            tenant_id=tenant_id_cv.get(),
            user_id=user_id,
            username=username_cv.get(),
            request_id=request_id_cv.get(),
            action=AuditAction.DELETE,
            table_name=obj.__tablename__,
            record_pk=str(obj.id),
            before_value=_get_full_data(obj),
        ))

# --- Post-Flush Listener to fill in missing Primary Keys ---
@event.listens_for(Session, "after_flush_postexec")
def after_flush_postexec(session: Session, flush_context):
    """
    After the flush is complete, update the audit logs with the newly generated
    primary keys for created objects.
    """
    if 'audit_pk_updates' in session.info:
        for parent_obj, audit_entry in session.info['audit_pk_updates']:
            if hasattr(parent_obj, 'id') and parent_obj.id is not None:
                audit_entry.record_pk = str(parent_obj.id)
        session.info['audit_pk_updates'].clear()
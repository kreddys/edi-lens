import logging
from contextvars import ContextVar
from typing import Dict, Any
from enum import Enum # <--- ADD THIS LINE

from sqlalchemy import event
from sqlalchemy.orm import Session, object_session
from sqlalchemy.orm.attributes import get_history

from src.models.audit_log import AuditLog, AuditAction

# Context variables to hold request-specific data.
# We use contextvars so this data is available throughout the request's async context.
user_id_cv: ContextVar[str] = ContextVar("user_id_cv", default=None)
username_cv: ContextVar[str] = ContextVar("username_cv", default=None)
tenant_id_cv: ContextVar[str] = ContextVar("tenant_id_cv", default=None)
request_id_cv: ContextVar[str] = ContextVar("request_id_cv", default=None)

logger = logging.getLogger(__name__)

# --- Helper Functions ---

# --- THIS IS THE FIX ---
# Create a helper to convert values to JSON-serializable types.
def _serialize_value(value: Any) -> Any:
    """Converts special types (like enums) to JSON-serializable formats."""
    if isinstance(value, Enum):
        return value.value
    return value

def _get_changed_data(obj) -> Dict[str, Any]:
    """Extracts changed data from a dirty SQLAlchemy object."""
    changes = {}
    for attr in obj.__mapper__.attrs:
        history = get_history(obj, attr.key)
        if history.has_changes():
            changes[attr.key] = {
                # Apply the serialization to the old and new values
                'old': _serialize_value(history.deleted[0]) if history.deleted else None,
                'new': _serialize_value(history.added[0]) if history.added else None,
            }
    return changes

def _get_full_data(obj) -> Dict[str, Any]:
    """Extracts all data from a new or deleted SQLAlchemy object."""
    # Apply the serialization to every value
    return {
        c.name: _serialize_value(getattr(obj, c.name))
        for c in obj.__table__.columns
    }


# --- The Main Event Listener ---
# (The rest of the file remains the same)

@event.listens_for(Session, "before_flush")
def before_flush(session: Session, flush_context, instances):
    """
    Listen for changes before they are flushed to the database and create audit logs.
    """
    # Short-circuit if we don't have a user context (e.g., for background tasks)
    user_id = user_id_cv.get()
    if not user_id:
        return

    # Process new, updated, and deleted objects
    for obj in session.new:
        if isinstance(obj, AuditLog):
            continue  # Avoid logging the audit log entries themselves
        
        session.add(AuditLog(
            tenant_id=tenant_id_cv.get(),
            user_id=user_id,
            username=username_cv.get(),
            request_id=request_id_cv.get(),
            action=AuditAction.CREATE,
            table_name=obj.__tablename__,
            record_pk=str(obj.id) if hasattr(obj, 'id') else None, # Needs flush to have ID
            after_value=_get_full_data(obj),
        ))

    for obj in session.dirty:
        if isinstance(obj, AuditLog):
            continue
            
        changed_data = _get_changed_data(obj)
        if changed_data: # Only log if there are actual changes
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
# This is needed because for new objects, the PK is not available in 'before_flush'.
@event.listens_for(Session, "after_flush")
def after_flush(session, flush_context):
    for obj in session.new:
        if isinstance(obj, AuditLog) and obj.action == AuditAction.CREATE and obj.record_pk is None:
            # At this point, the flushed object that triggered this log has its PK.
            # We need a way to link them. For now, we'll find it by table name and hope it's the only one.
            # A more robust solution might involve passing state between hooks.
            # For simplicity, we'll find the created object (that isn't an AuditLog).
            created_object = next(
                (
                    inst for inst in flush_context.mapped_objects
                    if inst.__tablename__ == obj.table_name and not isinstance(inst, AuditLog)
                ), 
                None
            )
            if created_object and hasattr(created_object, 'id'):
                obj.record_pk = str(created_object.id)
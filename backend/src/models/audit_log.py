import enum
from sqlalchemy import Column, Integer, String, Text, DateTime, Enum as SQLAlchemyEnum, JSON
from sqlalchemy.sql import func
from src.core.database import Base

class AuditAction(str, enum.Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"

class AuditLog(Base):
    __tablename__ = 'audit_logs'

    id = Column(Integer, primary_key=True, index=True)
    
    # Context columns (Who, where)
    tenant_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    username = Column(String, nullable=True) # Username might not always be present
    request_id = Column(String, nullable=True, index=True) # For tracing a single request

    # Event columns (What, when)
    timestamp_utc = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    action = Column(SQLAlchemyEnum(AuditAction), nullable=False)
    table_name = Column(String, nullable=False, index=True)
    record_pk = Column(String, nullable=False, index=True) # Use String for flexibility with UUIDs later

    # Data columns (The change itself)
    before_value = Column(JSON, nullable=True)
    after_value = Column(JSON, nullable=True)

    def __repr__(self):
        return (
            f"<AuditLog(id={self.id}, user='{self.username}', action='{self.action}', "
            f"table='{self.table_name}', record_pk='{self.record_pk}')>"
        )
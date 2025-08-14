# This file makes the 'models' directory a Python package and imports all models
# so that SQLAlchemy's Base can see them all when metadata is created.

from src.core.database import Base

# We do not manage tenants or users in our local DB with the Keycloak architecture
# from .tenant import Tenant
# from .user import User

# These are our core application models


from .audit_log import AuditLog
from .validation_transaction import ValidationTransaction

# General processing models
from .processing_log import ProcessingLog
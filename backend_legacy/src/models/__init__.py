# This file makes the 'models' directory a Python package and imports all models
# so that SQLAlchemy's Base can see them all when metadata is created.

from src.core.database import Base, configure_database_relationships

# Core application models - clean and focused on EDI processing
from .audit_log import AuditLog
from .validation_transaction import ValidationTransaction
from .processing_log import ProcessingLog

# Registry models
from .registry_models import RegistryTemplate, RegistryBucket
# Workflow models  
from .workflow_models import Workflow

# Legacy workflow models (OLD - will be removed)
# from .workflow_template import WorkflowTemplate, TemplateVersion, TemplateUsage, Workflow

# Configure SQLAlchemy relationships after all models are imported
# This ensures foreign key references can be properly resolved
configure_database_relationships()
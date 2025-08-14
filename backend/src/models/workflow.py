# FILE: backend/src/models/workflow.py

from sqlalchemy import Column, String, Text, JSON, DateTime, func, ARRAY, ForeignKey
from sqlalchemy.orm import relationship
from src.core.database import Base

class WorkflowTemplate(Base):
    __tablename__ = 'workflow_templates'

    template_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    category = Column(String, nullable=False)
    flow_definition = Column(JSON, nullable=False)
    configuration_schema = Column(JSON, nullable=False)
    deployment_method = Column(String, default='registry')
    nifi_registry_flow_id = Column(String)
    status = Column(String, default='ACTIVE')
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

class Workflow(Base):
    __tablename__ = 'workflows'

    workflow_id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    tags = Column(ARRAY(String))
    template_id = Column(String, ForeignKey('workflow_templates.template_id'))
    configuration = Column(JSON, nullable=False)
    status = Column(String, default='ACTIVE')
    nifi_process_group_id = Column(String)
    created_by = Column(String)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    template = relationship("WorkflowTemplate")

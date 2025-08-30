"""Remove legacy workflow template tables - replaced by Registry-first architecture

Revision ID: 727c3ba8c14a
Revises: c663b563a259
Create Date: 2025-08-30 04:53:52.598086

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '727c3ba8c14a'
down_revision: Union[str, Sequence[str], None] = 'c663b563a259'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove legacy workflow template tables - replaced by Registry-first architecture.
    
    These tables have been replaced by:
    - workflow_templates -> registry_templates (with Registry storage)
    - workflows -> workflow_instances (with Registry references)
    - template_versions -> Registry version control
    - template_usage -> Will be tracked differently
    
    Data was migrated before this removal.
    """
    # Drop legacy workflow template tables
    # Note: These were manually dropped before this migration was created
    # This migration documents the removal for proper version control
    
    # The following tables were removed:
    # - workflow_templates (replaced by registry_templates)
    # - template_versions (replaced by Registry version control)
    # - template_usage (will be tracked differently)
    # - workflows (replaced by workflow_instances)
    
    # Tables are already dropped, so this is a no-op for documentation
    pass


def downgrade() -> None:
    """Recreate legacy workflow template tables.
    
    WARNING: This will recreate the old table structure but without data.
    Only use this if you need to rollback to the old architecture.
    """
    # Recreate workflow_templates table
    op.create_table(
        'workflow_templates',
        sa.Column('template_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(), nullable=False),
        sa.Column('scope', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=True),
        sa.Column('maintainer', sa.String(), nullable=True),
        sa.Column('based_on', sa.String(), nullable=True),
        sa.Column('version', sa.String(), nullable=False, default='1.0'),
        sa.Column('flow_definition', sa.JSON(), nullable=False),
        sa.Column('configuration_schema', sa.JSON(), nullable=False),
        sa.Column('deployment_method', sa.String(), nullable=False, default='registry'),
        sa.Column('nifi_registry_flow_id', sa.String(), nullable=True),
        sa.Column('nifi_registry_bucket_id', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, default='ACTIVE'),
        sa.Column('is_featured', sa.Boolean(), nullable=False, default=False),
        sa.Column('usage_count', sa.Integer(), nullable=False, default=0),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deprecated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('template_id'),
        sa.CheckConstraint("scope IN ('GLOBAL', 'TENANT')", name='valid_scope'),
        sa.CheckConstraint(
            "(scope = 'GLOBAL' AND tenant_id IS NULL) OR (scope = 'TENANT' AND tenant_id IS NOT NULL)",
            name='tenant_scope_consistency'
        )
    )
    
    # Recreate template_versions table
    op.create_table(
        'template_versions',
        sa.Column('version_id', sa.String(), nullable=False),
        sa.Column('template_id', sa.String(), nullable=False),
        sa.Column('version', sa.String(), nullable=False),
        sa.Column('flow_definition', sa.JSON(), nullable=False),
        sa.Column('configuration_schema', sa.JSON(), nullable=False),
        sa.Column('changes', sa.Text(), nullable=True),
        sa.Column('created_by', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('is_current', sa.Boolean(), nullable=False, default=False),
        sa.Column('deployment_count', sa.Integer(), nullable=False, default=0),
        sa.PrimaryKeyConstraint('version_id'),
        sa.UniqueConstraint('template_id', 'version', name='uq_template_version')
    )
    
    # Recreate template_usage table
    op.create_table(
        'template_usage',
        sa.Column('usage_id', sa.String(), nullable=False),
        sa.Column('template_id', sa.String(), nullable=False),
        sa.Column('template_version', sa.String(), nullable=True),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('workflow_id', sa.String(), nullable=True),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('configuration_hash', sa.String(), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('usage_id')
    )
    
    # Recreate workflows table
    op.create_table(
        'workflows',
        sa.Column('workflow_id', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('template_id', sa.String(), nullable=False),
        sa.Column('configuration', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, default='ACTIVE'),
        sa.Column('nifi_process_group_id', sa.String(), nullable=True),
        sa.Column('nifi_parameter_context_id', sa.String(), nullable=True),
        sa.Column('deployment_method', sa.String(), nullable=True),
        sa.Column('flow_version', sa.Integer(), nullable=True),
        sa.Column('created_by', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('workflow_id'),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'PAUSED', 'ERROR', 'DELETED')", 
            name='valid_status'
        )
    )

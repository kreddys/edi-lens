"""Add UI configuration fields to workflow templates

Revision ID: add_ui_config_fields
Revises: da70c11e5c83
Create Date: 2025-08-18 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_ui_config_fields'
down_revision = 'da70c11e5c83'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add UI configuration fields to workflow_templates table."""
    # Add UI configuration fields
    op.add_column('workflow_templates', 
                  sa.Column('ui_configuration', postgresql.JSONB(astext_type=sa.Text()), nullable=True,
                           comment='WorkflowUIConfiguration for dynamic interface generation'))
    
    op.add_column('workflow_templates', 
                  sa.Column('input_specifications', postgresql.JSONB(astext_type=sa.Text()), nullable=True,
                           comment='Supported input types and constraints'))
    
    op.add_column('workflow_templates', 
                  sa.Column('output_specifications', postgresql.JSONB(astext_type=sa.Text()), nullable=True,
                           comment='Expected output definitions'))
    
    op.add_column('workflow_templates', 
                  sa.Column('processing_capabilities', sa.ARRAY(sa.Text()), nullable=True,
                           comment='Processing capabilities (e.g., validation, transformation)'))
    
    op.add_column('workflow_templates', 
                  sa.Column('supported_file_types', sa.ARRAY(sa.Text()), nullable=True,
                           comment='Supported file extensions'))
    
    op.add_column('workflow_templates', 
                  sa.Column('use_cases', sa.ARRAY(sa.Text()), nullable=True,
                           comment='Common use cases for this template'))
    
    op.add_column('workflow_templates', 
                  sa.Column('industry_tags', sa.ARRAY(sa.Text()), nullable=True,
                           comment='Industry-specific tags'))


def downgrade() -> None:
    """Remove UI configuration fields from workflow_templates table."""
    op.drop_column('workflow_templates', 'industry_tags')
    op.drop_column('workflow_templates', 'use_cases')
    op.drop_column('workflow_templates', 'supported_file_types')
    op.drop_column('workflow_templates', 'processing_capabilities')
    op.drop_column('workflow_templates', 'output_specifications')
    op.drop_column('workflow_templates', 'input_specifications')
    op.drop_column('workflow_templates', 'ui_configuration')
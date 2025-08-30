"""Add foreign key constraints for Registry models

Revision ID: ac1e6e39d124
Revises: 727c3ba8c14a
Create Date: 2025-08-30 05:15:37.877515

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ac1e6e39d124'
down_revision: Union[str, Sequence[str], None] = '727c3ba8c14a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add foreign key constraints for Registry models."""
    # Add foreign key constraint from workflow_instances to registry_templates
    op.create_foreign_key(
        'fk_workflow_instances_template_id',
        'workflow_instances',
        'registry_templates',
        ['template_id'],
        ['template_id'],
        ondelete='CASCADE'
    )


def downgrade() -> None:
    """Remove foreign key constraints for Registry models."""
    # Remove foreign key constraint
    op.drop_constraint('fk_workflow_instances_template_id', 'workflow_instances', type_='foreignkey')

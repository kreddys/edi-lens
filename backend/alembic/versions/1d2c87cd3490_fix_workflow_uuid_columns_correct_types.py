"""fix_workflow_uuid_columns_correct_types

Revision ID: 1d2c87cd3490
Revises: f3a23a715772
Create Date: 2025-09-02 16:35:20.453235

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '1d2c87cd3490'
down_revision: Union[str, Sequence[str], None] = 'f3a23a715772'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Fix UUID column types in workflows table using USING clause for conversion
    op.execute("ALTER TABLE public.workflows ALTER COLUMN template_id TYPE UUID USING template_id::UUID")
    op.execute("ALTER TABLE public.workflows ALTER COLUMN nifi_process_group_id TYPE UUID USING nifi_process_group_id::UUID")
    op.execute("ALTER TABLE public.workflows ALTER COLUMN nifi_parameter_context_id TYPE UUID USING nifi_parameter_context_id::UUID")


def downgrade() -> None:
    """Downgrade schema."""
    # Revert UUID column types back to VARCHAR
    op.alter_column('workflows', 'nifi_parameter_context_id',
               existing_type=sa.UUID(),
               type_=sa.VARCHAR(),
               existing_nullable=True,
               schema='public')
    op.alter_column('workflows', 'nifi_process_group_id',
               existing_type=sa.UUID(),
               type_=sa.VARCHAR(),
               existing_nullable=True,
               schema='public')
    op.alter_column('workflows', 'template_id',
               existing_type=sa.UUID(),
               type_=sa.VARCHAR(),
               existing_nullable=False,
               schema='public')

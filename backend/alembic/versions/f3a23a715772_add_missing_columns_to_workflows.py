"""add missing columns to workflows

Revision ID: f3a23a715772
Revises: 0b637794a1c5
Create Date: 2025-09-02 14:39:26.626969

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f3a23a715772'
down_revision: Union[str, Sequence[str], None] = '0b637794a1c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('workflows', sa.Column('nifi_registry_client_id', sa.String(), nullable=True), schema='public')
    op.add_column('workflows', sa.Column('version_control_info', postgresql.JSONB(astext_type=sa.Text()), nullable=True), schema='public')
    op.add_column('workflows', sa.Column('deployed_at', sa.DateTime(timezone=True), nullable=True), schema='public')
    op.add_column('workflows', sa.Column('last_started_at', sa.DateTime(timezone=True), nullable=True), schema='public')
    op.add_column('workflows', sa.Column('last_stopped_at', sa.DateTime(timezone=True), nullable=True), schema='public')
    op.alter_column('workflows', 'template_version',
               existing_type=sa.INTEGER(),
               nullable=False,
               schema='public')

def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('workflows', 'template_version',
               existing_type=sa.INTEGER(),
               nullable=True,
               schema='public')
    op.drop_column('workflows', 'last_stopped_at', schema='public')
    op.drop_column('workflows', 'last_started_at', schema='public')
    op.drop_column('workflows', 'deployed_at', schema='public')
    op.drop_column('workflows', 'version_control_info', schema='public')
    op.drop_column('workflows', 'nifi_registry_client_id', schema='public')
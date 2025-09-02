"""add template_version to workflows

Revision ID: 0b637794a1c5
Revises: ac1e6e39d124
Create Date: 2025-09-02 14:37:59.622358

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0b637794a1c5'
down_revision: Union[str, Sequence[str], None] = 'ac1e6e39d124'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('workflows', sa.Column('template_version', sa.Integer(), nullable=True), schema='public')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('workflows', 'template_version', schema='public')
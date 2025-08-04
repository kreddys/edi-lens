"""enhance_partner_profiles_for_validation_config

Revision ID: 78b585c37c59
Revises: 50a46f3ffa51
Create Date: 2025-08-04 04:42:11.521408

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '78b585c37c59'
down_revision: Union[str, Sequence[str], None] = '50a46f3ffa51'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Enhance partner_profiles with validation configuration fields."""
    # Add validation configuration fields to partner_profiles
    op.add_column('partner_profiles', sa.Column('snip_level', sa.String(10), nullable=False, server_default='SNIP3'))
    op.add_column('partner_profiles', sa.Column('generate_ta1', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('partner_profiles', sa.Column('generate_999', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('partner_profiles', sa.Column('custom_validation_rules', sa.JSON(), nullable=True))
    
    # Add timestamps for tracking
    op.add_column('partner_profiles', sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True))
    op.add_column('partner_profiles', sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True))
    
    # Enhance processing_logs if it exists (from SFTP implementation)
    # Check if processing_logs table exists first
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if 'processing_logs' in inspector.get_table_names(schema='public'):
        op.add_column('processing_logs', sa.Column('profile_id', sa.Integer(), nullable=True))
        op.add_column('processing_logs', sa.Column('snip_level_used', sa.String(10), nullable=True))
        op.add_column('processing_logs', sa.Column('ta1_999_generated', sa.Boolean(), nullable=False, server_default='false'))
        
        # Add foreign key constraint for profile_id
        op.create_foreign_key('fk_processing_logs_profile_id', 'processing_logs', 'partner_profiles', ['profile_id'], ['id'])
    else:
        # Create processing_logs table if it doesn't exist
        op.create_table('processing_logs',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('tenant_id', sa.String(50), nullable=False),
            sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('source', sa.String(10), nullable=False),  # 'API' or 'SFTP'
            sa.Column('file_name', sa.String(255), nullable=True),
            sa.Column('file_size_bytes', sa.Integer(), nullable=True),
            sa.Column('validation_result', sa.String(10), nullable=False),  # 'VALID', 'INVALID', 'ERROR'
            sa.Column('processing_time_ms', sa.Integer(), nullable=True),
            sa.Column('error_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('schema_name', sa.String(255), nullable=True),
            sa.Column('snip_level_used', sa.String(10), nullable=True),
            sa.Column('profile_id', sa.Integer(), nullable=True),
            sa.Column('ta1_generated', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('ta1_999_generated', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('original_content_path', sa.String(500), nullable=True),
            sa.Column('ta1_content_path', sa.String(500), nullable=True),
            sa.Column('ta1_999_content_path', sa.String(500), nullable=True),
            schema='public'
        )
        
        # Add indexes for performance
        op.create_index('ix_processing_logs_tenant_timestamp', 'processing_logs', ['tenant_id', 'timestamp'])
        op.create_index('ix_processing_logs_validation_result', 'processing_logs', ['validation_result'])
        op.create_index('ix_processing_logs_source', 'processing_logs', ['source'])
        
        # Add foreign key constraint
        op.create_foreign_key('fk_processing_logs_profile_id', 'processing_logs', 'partner_profiles', ['profile_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema - remove enhanced validation configuration fields."""
    # Check if processing_logs table exists and was created by this migration
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    if 'processing_logs' in inspector.get_table_names(schema='public'):
        # Drop foreign key constraint first
        op.drop_constraint('fk_processing_logs_profile_id', 'processing_logs', type_='foreignkey')
        
        # Check if these columns were added by this migration (have the new columns)
        columns = [col['name'] for col in inspector.get_columns('processing_logs', schema='public')]
        
        if 'profile_id' in columns and 'snip_level_used' in columns and 'ta1_999_generated' in columns:
            # This looks like our enhanced version - drop the columns we added
            op.drop_column('processing_logs', 'ta1_999_generated')
            op.drop_column('processing_logs', 'snip_level_used') 
            op.drop_column('processing_logs', 'profile_id')
        else:
            # This table was created entirely by this migration - drop it
            op.drop_table('processing_logs')
    
    # Remove validation configuration fields from partner_profiles
    op.drop_column('partner_profiles', 'updated_at')
    op.drop_column('partner_profiles', 'created_at')
    op.drop_column('partner_profiles', 'custom_validation_rules')
    op.drop_column('partner_profiles', 'generate_999')
    op.drop_column('partner_profiles', 'generate_ta1')
    op.drop_column('partner_profiles', 'snip_level')

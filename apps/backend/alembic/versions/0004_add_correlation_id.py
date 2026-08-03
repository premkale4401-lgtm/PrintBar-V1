"""add correlation_id

Revision ID: 0004_add_correlation_id
Revises: 0003_add_gateway_event_id_to_webhooks
Create Date: 2026-08-04 00:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0004_add_correlation_id'
down_revision: Union[str, None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add correlation_id to uploaded_files
    op.add_column('uploaded_files', sa.Column('correlation_id', sa.String(length=128), server_default='unknown', nullable=False))
    op.create_index(op.f('ix_uploaded_files_correlation_id'), 'uploaded_files', ['correlation_id'], unique=False)
    
    # Add correlation_id to print_jobs
    op.add_column('print_jobs', sa.Column('correlation_id', sa.String(length=128), server_default='unknown', nullable=False))
    op.create_index(op.f('ix_print_jobs_correlation_id'), 'print_jobs', ['correlation_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_print_jobs_correlation_id'), table_name='print_jobs')
    op.drop_column('print_jobs', 'correlation_id')
    
    op.drop_index(op.f('ix_uploaded_files_correlation_id'), table_name='uploaded_files')
    op.drop_column('uploaded_files', 'correlation_id')

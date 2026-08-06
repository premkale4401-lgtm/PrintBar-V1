"""add performance indexes

Revision ID: 0005_add_performance_indexes
Revises: eda705356a7f
Create Date: 2026-08-06 07:25:00.000000

Adds composite and covering indexes to support high-throughput
production workloads (1000+ consecutive jobs).

Indexes added:
    - print_jobs(status, created_at)  — FIFO queue query (status=QUEUED ORDER BY created_at ASC)
    - print_jobs(kiosk_id, status)    — active job lookup by kiosk (recovery, heartbeat)
    - print_jobs(session_id, status)  — session job status polling
    - kiosks(status, ws_connected)    — online kiosk lookup by dispatcher
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0005_add_performance_indexes'
down_revision: Union[str, None] = 'eda705356a7f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Composite index for FIFO queue query:
    #   SELECT * FROM print_jobs WHERE status = 'QUEUED' ORDER BY created_at ASC
    # This is the most critical query — executed by every dispatch cycle.
    op.create_index(
        'ix_print_jobs_status_created_at',
        'print_jobs',
        ['status', 'created_at'],
        unique=False,
    )

    # Composite index for active job lookup by kiosk:
    #   SELECT * FROM print_jobs WHERE kiosk_id = ? AND status IN (...)
    # Used by recovery service and heartbeat monitor.
    op.create_index(
        'ix_print_jobs_kiosk_id_status',
        'print_jobs',
        ['kiosk_id', 'status'],
        unique=False,
    )

    # Composite index for session job status polling:
    #   SELECT * FROM print_jobs WHERE session_id = ? AND status IN (...)
    # Used by frontend status polling endpoint.
    op.create_index(
        'ix_print_jobs_session_id_status',
        'print_jobs',
        ['session_id', 'status'],
        unique=False,
    )

    # Composite index for kiosk online lookup:
    #   SELECT * FROM kiosks WHERE status IN ('ONLINE', 'PRINTING') AND is_active = TRUE
    # Used by job dispatcher on every dispatch cycle.
    op.create_index(
        'ix_kiosks_status_ws_connected',
        'kiosks',
        ['status', 'ws_connected'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_kiosks_status_ws_connected', table_name='kiosks')
    op.drop_index('ix_print_jobs_session_id_status', table_name='print_jobs')
    op.drop_index('ix_print_jobs_kiosk_id_status', table_name='print_jobs')
    op.drop_index('ix_print_jobs_status_created_at', table_name='print_jobs')

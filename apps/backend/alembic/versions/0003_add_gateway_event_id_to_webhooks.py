"""Add gateway_event_id to webhooks

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-03 18:32:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0003'
down_revision: Union[str, None] = '0002_seed_pricing_rules'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add the new column
    op.add_column('payment_webhooks', sa.Column('gateway_event_id', sa.String(length=256), nullable=True))
    
    # Create the new index and unique constraint
    op.create_index(op.f('ix_payment_webhooks_gateway_event_id'), 'payment_webhooks', ['gateway_event_id'], unique=True)
    
    # Drop the unique constraint on gateway_txn_id
    # We must drop the unique index that was created for gateway_txn_id
    op.drop_index('ix_payment_webhooks_gateway_txn_id', table_name='payment_webhooks')
    op.create_index(op.f('ix_payment_webhooks_gateway_txn_id'), 'payment_webhooks', ['gateway_txn_id'], unique=False)


def downgrade() -> None:
    # Re-add the unique constraint on gateway_txn_id
    op.drop_index(op.f('ix_payment_webhooks_gateway_txn_id'), table_name='payment_webhooks')
    op.create_index('ix_payment_webhooks_gateway_txn_id', 'payment_webhooks', ['gateway_txn_id'], unique=True)
    
    # Drop the gateway_event_id column and index
    op.drop_index(op.f('ix_payment_webhooks_gateway_event_id'), table_name='payment_webhooks')
    op.drop_column('payment_webhooks', 'gateway_event_id')

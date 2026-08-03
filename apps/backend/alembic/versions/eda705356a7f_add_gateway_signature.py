from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = 'eda705356a7f'
down_revision: Union[str, None] = '0004_add_correlation_id'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('payments', sa.Column('gateway_signature', sa.String(length=256), nullable=True))
    op.add_column('payments', sa.Column('verification_time', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('payments', 'verification_time')
    op.drop_column('payments', 'gateway_signature')

"""sites.consecutive_failures for auto-disable-on-failure

Revision ID: b7d4f0a2c9e1
Revises: a1c3f9e2b7d4
Create Date: 2026-09-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7d4f0a2c9e1'
down_revision: Union[str, Sequence[str], None] = 'a1c3f9e2b7d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'sites',
        sa.Column('consecutive_failures', sa.Integer(), nullable=False, server_default='0'),
    )


def downgrade() -> None:
    op.drop_column('sites', 'consecutive_failures')

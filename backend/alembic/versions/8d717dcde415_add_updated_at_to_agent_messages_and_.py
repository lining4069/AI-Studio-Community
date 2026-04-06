"""add updated_at to agent_messages and agent_steps

Revision ID: 8d717dcde415
Revises: 2026_04_06_0001
Create Date: 2026-04-07 02:20:33.506958

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8d717dcde415'
down_revision: Union[str, Sequence[str], None] = '2026_04_06_0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add updated_at column to agent_messages and agent_steps tables."""
    op.add_column(
        'agent_messages',
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text('CURRENT_TIMESTAMP'),
        ),
    )
    op.add_column(
        'agent_steps',
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text('CURRENT_TIMESTAMP'),
        ),
    )


def downgrade() -> None:
    """Remove updated_at column from agent_messages and agent_steps tables."""
    op.drop_column('agent_messages', 'updated_at')
    op.drop_column('agent_steps', 'updated_at')

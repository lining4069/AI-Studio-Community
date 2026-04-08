"""add agent_mcp_servers table for Phase 3

Revision ID: xxxx
Revises: a0e39394ac41
Create Date: 2026-04-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'xxxx'
down_revision: Union[str, Sequence[str], None] = 'a0e39394ac41'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Phase 3 changes:
    1. Create agent_mcp_servers table for MCP tool configuration
    """
    op.create_table(
        'agent_mcp_servers',
        sa.Column('id', sa.String(length=64), nullable=False, primary_key=True),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('url', sa.String(length=500), nullable=False),
        sa.Column('headers', sa.JSON(), nullable=True),
        sa.Column('transport', sa.String(length=20), nullable=False, server_default='streamable_http'),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('agent_mcp_servers')

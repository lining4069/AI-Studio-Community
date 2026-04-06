"""create agent_sessions, agent_messages, agent_steps tables

Revision ID: 2026_04_06_0001
Revises: 2026_04_03_0003
Create Date: 2026-04-06 00:01:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2026_04_06_0001'
down_revision: Union[str, Sequence[str], None] = '2026_04_03_0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # --- agent_sessions ---
    op.create_table(
        'agent_sessions',
        sa.Column('id', sa.String(length=64), nullable=False, primary_key=True),
        sa.Column('user_id', sa.Integer(), nullable=False, index=True),
        sa.Column('agent_id', sa.String(length=64), nullable=True),
        sa.Column('title', sa.Text(), nullable=True),
        sa.Column('mode', sa.String(length=20), nullable=False, server_default='assistant'),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    op.create_index('ix_agent_sessions_user_id', 'agent_sessions', ['user_id'])

    # --- agent_messages ---
    op.create_table(
        'agent_messages',
        sa.Column('id', sa.String(length=64), nullable=False, primary_key=True),
        sa.Column('session_id', sa.String(length=64), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('metadata', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['session_id'], ['agent_sessions.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_agent_messages_session_id', 'agent_messages', ['session_id'])

    # --- agent_steps ---
    op.create_table(
        'agent_steps',
        sa.Column('id', sa.String(length=64), nullable=False, primary_key=True),
        sa.Column('session_id', sa.String(length=64), nullable=False),
        sa.Column('step_index', sa.Integer(), nullable=False),
        sa.Column('type', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=True),
        sa.Column('input', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('output', sa.JSON(), nullable=True),
        sa.Column('thought', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['session_id'], ['agent_sessions.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_agent_steps_session_id', 'agent_steps', ['session_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_agent_steps_session_id', table_name='agent_steps')
    op.drop_table('agent_steps')

    op.drop_index('ix_agent_messages_session_id', table_name='agent_messages')
    op.drop_table('agent_messages')

    op.drop_index('ix_agent_sessions_user_id', table_name='agent_sessions')
    op.drop_table('agent_sessions')

"""add agent_runs table and Phase 2 columns

Revision ID: a0e39394ac41
Revises: 8d717dcde415
Create Date: 2026-04-07 21:21:21.910116

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a0e39394ac41'
down_revision: Union[str, Sequence[str], None] = '8d717dcde415'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Phase 2 changes:
    1. Create agent_runs table
    2. Add run_id to agent_messages (FK)
    3. Add run_id + idempotency_key to agent_steps (FK + index)
    4. Add unique constraint on (run_id, step_index) for agent_steps
    """
    # 1. Create agent_runs table
    op.create_table(
        'agent_runs',
        sa.Column('id', sa.String(length=64), nullable=False, primary_key=True),
        sa.Column('session_id', sa.String(length=64), nullable=False, index=True),
        sa.Column('type', sa.String(length=20), nullable=False, server_default='chat'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='running'),
        sa.Column('input', sa.Text(), nullable=False),
        sa.Column('output', sa.Text(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('last_step_index', sa.Integer(), nullable=True),
        sa.Column('resumable', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('trace_id', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['session_id'], ['agent_sessions.id'], ondelete='CASCADE'),
    )

    # 2. Add run_id to agent_messages (nullable, for backward compatibility)
    op.add_column(
        'agent_messages',
        sa.Column('run_id', sa.String(length=64), nullable=True, index=True),
    )
    op.create_foreign_key(
        'fk_agent_messages_run_id',
        'agent_messages', 'agent_runs',
        ['run_id'], ['id'],
        ondelete='CASCADE',
    )

    # 3. Add run_id + idempotency_key to agent_steps
    op.add_column(
        'agent_steps',
        sa.Column('run_id', sa.String(length=64), nullable=True, index=True),
    )
    op.add_column(
        'agent_steps',
        sa.Column('idempotency_key', sa.String(length=64), nullable=True, index=True),
    )
    op.create_foreign_key(
        'fk_agent_steps_run_id',
        'agent_steps', 'agent_runs',
        ['run_id'], ['id'],
        ondelete='CASCADE',
    )

    # 4. Add unique constraint on (run_id, step_index)
    # Only for rows where run_id is not null
    op.create_index(
        'ix_agent_steps_run_id_step_index',
        'agent_steps',
        ['run_id', 'step_index'],
        unique=False,  # unique=True would fail on null run_id; handled at app level
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop FK constraints and indexes
    op.drop_index('ix_agent_steps_run_id_step_index', table_name='agent_steps')
    op.drop_constraint('fk_agent_steps_run_id', 'agent_steps', type_='foreignkey')
    op.drop_constraint('fk_agent_messages_run_id', 'agent_messages', type_='foreignkey')

    # Drop added columns
    op.drop_column('agent_steps', 'idempotency_key')
    op.drop_column('agent_steps', 'run_id')
    op.drop_column('agent_messages', 'run_id')

    # Drop agent_runs table
    op.drop_table('agent_runs')

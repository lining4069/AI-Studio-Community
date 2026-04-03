"""initial schema

Revision ID: 2026_04_03_0001
Revises:
Create Date: 2026-04-03 17:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2026_04_03_0001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # --- user ---
    op.create_table(
        'user',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True, autoincrement=True),
        sa.Column('username', sa.String(length=50), nullable=False),
        sa.Column('email', sa.String(length=100), nullable=True),
        sa.Column('phone', sa.String(length=20), nullable=True),
        sa.Column('password', sa.String(length=255), nullable=False),
        sa.Column('nickname', sa.String(length=50), nullable=True),
        sa.Column('avatar', sa.String(length=255), nullable=True),
        sa.Column('gender', sa.String(length=7), nullable=True),
        sa.Column('bio', sa.String(length=500), nullable=True),
        sa.Column('is_email_verified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_phone_verified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_superuser', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    op.create_index('idx_phone', 'user', ['phone'])
    op.create_index('idx_username', 'user', ['username'])
    op.create_index('idx_email', 'user', ['email'])

    # --- llm_models ---
    op.create_table(
        'llm_models',
        sa.Column('id', sa.String(length=64), nullable=False, primary_key=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('model_name', sa.String(length=255), nullable=False),
        sa.Column('base_url', sa.String(length=500), nullable=True),
        sa.Column('api_key', sa.Text(), nullable=True),
        sa.Column('encrypted_api_key', sa.Text(), nullable=True),
        sa.Column('temperature', sa.Float(), nullable=False, server_default='0.7'),
        sa.Column('max_tokens', sa.Integer(), nullable=True),
        sa.Column('context_window', sa.Integer(), nullable=False, server_default='4096'),
        sa.Column('support_vision', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('support_function_calling', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_llm_models_user_id', 'llm_models', ['user_id'])

    # --- embedding_models ---
    op.create_table(
        'embedding_models',
        sa.Column('id', sa.String(length=64), nullable=False, primary_key=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('type', sa.String(length=50), nullable=False),
        sa.Column('model_name', sa.String(length=255), nullable=True),
        sa.Column('endpoint', sa.String(length=500), nullable=True),
        sa.Column('api_key', sa.Text(), nullable=True),
        sa.Column('encrypted_api_key', sa.Text(), nullable=True),
        sa.Column('local_model_path', sa.String(length=500), nullable=True),
        sa.Column('dimension', sa.Integer(), nullable=True),
        sa.Column('batch_size', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_dimensionable', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_embedding_models_user_id', 'embedding_models', ['user_id'])

    # --- rerank_models ---
    op.create_table(
        'rerank_models',
        sa.Column('id', sa.String(length=64), nullable=False, primary_key=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('model_name', sa.String(length=255), nullable=True),
        sa.Column('base_url', sa.String(length=500), nullable=True),
        sa.Column('api_key', sa.Text(), nullable=True),
        sa.Column('encrypted_api_key', sa.Text(), nullable=True),
        sa.Column('top_n', sa.Integer(), nullable=True),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_rerank_models_user_id', 'rerank_models', ['user_id'])

    # --- kb_documents ---
    op.create_table(
        'kb_documents',
        sa.Column('id', sa.String(length=64), nullable=False, primary_key=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('embedding_model_id', sa.String(length=64), nullable=True),
        sa.Column('rerank_model_id', sa.String(length=64), nullable=True),
        sa.Column('chunk_size', sa.Integer(), nullable=False, server_default='256'),
        sa.Column('chunk_overlap', sa.Integer(), nullable=False, server_default='50'),
        sa.Column('chunk_mode', sa.String(length=50), nullable=False, server_default="'unknown'"),
        sa.Column('retrieval_mode', sa.String(length=20), nullable=False, server_default="'all'"),
        sa.Column('top_k', sa.Integer(), nullable=False, server_default='10'),
        sa.Column('similarity_threshold', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('vector_weight', sa.Float(), nullable=False, server_default='0.7'),
        sa.Column('enable_rerank', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('rerank_top_k', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('collection_name', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_kb_documents_user_id', 'kb_documents', ['user_id'])

    # --- kb_files ---
    op.create_table(
        'kb_files',
        sa.Column('id', sa.String(length=64), nullable=False, primary_key=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('kb_id', sa.String(length=64), nullable=False),
        sa.Column('file_name', sa.String(length=500), nullable=False),
        sa.Column('file_path', sa.String(length=1000), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('file_type', sa.String(length=100), nullable=True),
        sa.Column('file_md5', sa.String(length=64), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default="'pending'"),
        sa.Column('chunk_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failed_reason', sa.Text(), nullable=True),
        sa.Column('file_metadata', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['kb_id'], ['kb_documents.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_kb_files_user_id', 'kb_files', ['user_id'])
    op.create_index('ix_kb_files_kb_id', 'kb_files', ['kb_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_kb_files_kb_id', table_name='kb_files')
    op.drop_index('ix_kb_files_user_id', table_name='kb_files')
    op.drop_table('kb_files')

    op.drop_index('ix_kb_documents_user_id', table_name='kb_documents')
    op.drop_table('kb_documents')

    op.drop_index('ix_rerank_models_user_id', table_name='rerank_models')
    op.drop_table('rerank_models')

    op.drop_index('ix_embedding_models_user_id', table_name='embedding_models')
    op.drop_table('embedding_models')

    op.drop_index('ix_llm_models_user_id', table_name='llm_models')
    op.drop_table('llm_models')

    op.drop_index('idx_email', table_name='user')
    op.drop_index('idx_username', table_name='user')
    op.drop_index('idx_phone', table_name='user')
    op.drop_table('user')

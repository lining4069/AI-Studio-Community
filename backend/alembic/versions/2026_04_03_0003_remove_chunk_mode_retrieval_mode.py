"""remove_chunk_mode_and_retrieval_mode

Revision ID: 2026_04_03_0003
Revises: 2026_04_03_0002
Create Date: 2026-04-03 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '2026_04_03_0003'
down_revision: Union[str, Sequence[str], None] = '2026_04_03_0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove redundant fields from kb_documents table.

    - chunk_mode: chunking strategy is now file-type driven, not KB-level config
    - retrieval_mode: always uses hybrid retrieval (dense + sparse), field never生效
    """
    op.drop_column('kb_documents', 'chunk_mode')
    op.drop_column('kb_documents', 'retrieval_mode')


def downgrade() -> None:
    """Re-add removed columns (for rollback)."""
    op.add_column('kb_documents', op.column('chunk_mode', op.sa.String(length=50), nullable=True, server_default='recursive'))
    op.add_column('kb_documents', op.column('retrieval_mode', op.sa.String(length=20), nullable=True, server_default='hybrid'))

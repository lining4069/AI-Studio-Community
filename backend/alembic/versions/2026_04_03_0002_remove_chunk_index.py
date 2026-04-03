"""remove_chunk_index

Revision ID: 2026_04_03_0002
Revises: 2026_04_03_0001
Create Date: 2026-04-03 17:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2026_04_03_0002'
down_revision: Union[str, Sequence[str], None] = '2026_04_03_0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove chunk_index column from Raw SQL tables."""
    # pg_chunks: chunk_index column is unused in retrieval/sort/filter
    op.drop_column('pg_chunks', 'chunk_index', schema=None)

    # pg_sparse_chunks: chunk_index column is unused in retrieval/sort/filter
    op.drop_column('pg_sparse_chunks', 'chunk_index', schema=None)


def downgrade() -> None:
    """Re-add chunk_index column (for rollback)."""
    op.add_column('pg_chunks', sa.Column('chunk_index', sa.Integer(), nullable=True))
    op.add_column('pg_sparse_chunks', sa.Column('chunk_index', sa.Integer(), nullable=True))

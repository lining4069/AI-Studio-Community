"""add_is_dimensionable_to_embedding_models

Revision ID: 90f5c8a7e2b1
Revises: ad34aaa
Create Date: 2026-03-31 18:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "90f5c8a7e2b1"
down_revision: Union[str, Sequence[str], None] = "d7cc0b95c3d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add is_dimensionable column to embedding_models."""
    op.add_column(
        "embedding_models",
        sa.Column("is_dimensionable", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
    )


def downgrade() -> None:
    """Remove is_dimensionable column from embedding_models."""
    op.drop_column("embedding_models", "is_dimensionable")

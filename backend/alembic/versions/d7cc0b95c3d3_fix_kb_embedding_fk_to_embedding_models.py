"""fix_kb_embedding_fk_to_embedding_models

Revision ID: d7cc0b95c3d3
Revises: 0d05ffe676a0
Create Date: 2026-03-31 17:35:49.337539

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd7cc0b95c3d3'
down_revision: Union[str, Sequence[str], None] = '0d05ffe676a0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Fix embedding_model_id FK: was referencing llm_models, should reference embedding_models
    # First drop the wrong FK
    op.drop_constraint("kb_documents_ibfk_1", "kb_documents", type_="foreignkey")
    # Then add the correct FK (column already exists, just needs proper constraint)
    op.create_foreign_key(
        "kb_documents_ibfk_1",
        "kb_documents", "embedding_models",
        ["embedding_model_id"], ["id"],
        ondelete="SET NULL"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("kb_documents_ibfk_1", "kb_documents", type_="foreignkey")
    op.create_foreign_key(
        "kb_documents_ibfk_1",
        "kb_documents", "llm_models",
        ["embedding_model_id"], ["id"],
        ondelete="SET NULL"
    )

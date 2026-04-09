"""add stdio columns to agent_mcp_servers

Revision ID: 2026_04_09_0001
Revises: 2026_04_08_0002
Create Date: 2026-04-09

Phase 5: MCP Native SDK 重构，添加 stdio 传输支持
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2026_04_09_0001"
down_revision: Union[str, Sequence[str], None] = "2026_04_08_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add stdio columns for Phase 5 MCP Native SDK support.

    新增字段：
    - command: stdio 进程命令
    - args: stdio 进程参数
    - env: stdio 环境变量
    - cwd: stdio 工作目录

    Note: user_id 已在早期迁移中添加
    """
    op.add_column(
        "agent_mcp_servers",
        sa.Column("command", sa.String(length=500), nullable=True)
    )
    op.add_column(
        "agent_mcp_servers",
        sa.Column("args", sa.JSON(), nullable=True)
    )
    op.add_column(
        "agent_mcp_servers",
        sa.Column("env", sa.JSON(), nullable=True)
    )
    op.add_column(
        "agent_mcp_servers",
        sa.Column("cwd", sa.String(length=500), nullable=True)
    )


def downgrade() -> None:
    """Remove stdio columns."""
    op.drop_column("agent_mcp_servers", "cwd")
    op.drop_column("agent_mcp_servers", "env")
    op.drop_column("agent_mcp_servers", "args")
    op.drop_column("agent_mcp_servers", "command")

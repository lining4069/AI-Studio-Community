"""Add agent_configs and snapshot - Phase 4

Revision ID: 2026_04_08_0002
Revises: 2026_04_08_0001
Create Date: 2026-04-08

Phase 4 tables:
- agent_configs: Configuration templates for agents/assistants
- agent_config_tools: Built-in tool configs with per-tool settings
- agent_config_mcp_servers: MCP server links
- agent_config_kbs: Knowledge base links

Changes:
- agent_sessions: add config_id FK
- agent_runs: add config_snapshot JSONB
- agent_mcp_servers: add user_id FK (safe migration for existing data)
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers
revision = "2026_04_08_0002"
down_revision = "2026_04_08_0001"  # Phase 3 migration
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Step 1: Create agent_configs table
    op.create_table(
        "agent_configs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("llm_model_id", sa.String(64), nullable=True),
        sa.Column("agent_type", sa.String(20), nullable=False, server_default="simple"),
        sa.Column("max_loop", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_index("idx_agent_configs_user_id", "agent_configs", ["user_id"])

    # Step 2: Create agent_config_tools
    # NOTE: column is tool_config (not config) to avoid SQLAlchemy relationship name conflict
    op.create_table(
        "agent_config_tools",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "config_id",
            sa.String(64),
            sa.ForeignKey("agent_configs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tool_name", sa.String(50), nullable=False),
        sa.Column(
            "tool_config",
            JSONB(),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.UniqueConstraint(
            "config_id", "tool_name", name="uq_config_tool"
        ),
    )
    op.create_index("idx_agent_config_tools_config_id", "agent_config_tools", ["config_id"])

    # Step 3: Create agent_config_mcp_servers
    op.create_table(
        "agent_config_mcp_servers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "config_id",
            sa.String(64),
            sa.ForeignKey("agent_configs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "mcp_server_id",
            sa.String(64),
            sa.ForeignKey("agent_mcp_servers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "config_id", "mcp_server_id", name="uq_config_mcp"
        ),
    )
    op.create_index(
        "idx_agent_config_mcp_config_id",
        "agent_config_mcp_servers",
        ["config_id"],
    )

    # Step 4: Create agent_config_kbs
    op.create_table(
        "agent_config_kbs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "config_id",
            sa.String(64),
            sa.ForeignKey("agent_configs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kb_id", sa.String(64), nullable=False),
        sa.Column(
            "kb_config",
            JSONB(),
            nullable=False,
            server_default="{}",
        ),
        sa.UniqueConstraint("config_id", "kb_id", name="uq_config_kb"),
    )
    op.create_index(
        "idx_agent_config_kbs_config_id", "agent_config_kbs", ["config_id"]
    )

    # Step 5: agent_sessions add config_id FK
    op.add_column(
        "agent_sessions",
        sa.Column(
            "config_id",
            sa.String(64),
            sa.ForeignKey("agent_configs.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("idx_agent_sessions_config_id", "agent_sessions", ["config_id"])

    # Step 6: agent_runs add config_snapshot
    op.add_column(
        "agent_runs",
        sa.Column("config_snapshot", JSONB(), nullable=True),
    )

    # Step 7: agent_mcp_servers add user_id FK (safe migration)
    # 7a: Add nullable column first
    op.add_column(
        "agent_mcp_servers",
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("user.id"),
            nullable=True,
        ),
    )

    # 7b: For existing records, set user_id to a system user (e.g., user_id=1)
    # NOTE: In production, you may need to prompt or handle this differently
    op.execute(
        "UPDATE agent_mcp_servers SET user_id = 1 WHERE user_id IS NULL"
    )

    # 7c: Set NOT NULL (data is now guaranteed non-null)
    op.alter_column(
        "agent_mcp_servers", "user_id", existing_type=sa.Integer(), nullable=False
    )

    # 7d: Add unique constraint
    op.create_index(
        "idx_agent_mcp_servers_user_id", "agent_mcp_servers", ["user_id"]
    )
    op.create_unique_constraint(
        "uq_mcp_server_user_name",
        "agent_mcp_servers",
        ["user_id", "name"],
    )


def downgrade() -> None:
    # Drop indexes and constraints
    op.drop_index("idx_agent_mcp_servers_user_id", "agent_mcp_servers")
    op.drop_constraint(
        "uq_mcp_server_user_name", "agent_mcp_servers", type_="unique"
    )
    op.drop_column("agent_mcp_servers", "user_id")

    op.drop_column("agent_runs", "config_snapshot")

    op.drop_index("idx_agent_sessions_config_id", "agent_sessions")
    op.drop_column("agent_sessions", "config_id")

    op.drop_table("agent_config_kbs")
    op.drop_table("agent_config_mcp_servers")
    op.drop_table("agent_config_tools")
    op.drop_table("agent_configs")

"""
Alembic migration environment configuration.

关键设计：
1. 数据库连接 URL 完全从 .env.${ENVIRONMENT} 读取，由 app.core.settings.Settings 管理
2. 所有 ORM 模型必须在此导入，以确保 autogenerate 能检测到 schema 变化
3. Raw SQL 表（pg_chunks、pg_sparse_chunks）由手写迁移管理，不走 ORM
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# 导入配置管理
from app.core.settings import get_settings
from app.common.base import Base

# 导入所有 ORM 模型（供 autogenerate 使用）
from app.modules.users.models import User  # noqa: F401
from app.modules.llm_model.models import LlmModel  # noqa: F401
from app.modules.embedding_model.models import EmbeddingModel  # noqa: F401
from app.modules.rerank_model.models import RerankModel  # noqa: F401
from app.modules.knowledge_base.models import KbDocument, KbFile  # noqa: F401
from app.modules.agent.models import AgentSession, AgentMessage, AgentStep  # noqa: F401

# Alembic Config object
config = context.config

# 从 Settings 注入真实的数据库 URL（覆盖 alembic.ini 中的 placeholder）
settings = get_settings()
if settings.DATABASE_TYPE == "postgresql":
    db_url = (
        f"postgresql+asyncpg://{settings.DATABASE_USER}:{settings.DATABASE_PASSWORD}"
        f"@{settings.DATABASE_HOST}:{settings.DATABASE_PORT}/{settings.DATABASE_NAME}"
    )
elif settings.DATABASE_TYPE == "mysql":
    db_url = (
        f"mysql+aiomysql://{settings.DATABASE_USER}:{settings.DATABASE_PASSWORD}"
        f"@{settings.DATABASE_HOST}:{settings.DATABASE_PORT}/{settings.DATABASE_NAME}?charset=utf8mb4"
    )
else:
    db_url = f"sqlite+aiosqlite:///{settings.DATABASE_NAME}"

config.set_main_option("sqlalchemy.url", db_url)

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ORM 模型的 metadata，供 autogenerate 使用
target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# Offline mode（生成 SQL 脚本，不连接数据库）
# ---------------------------------------------------------------------------


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    生成 SQL 脚本文件（用于无 DB 连接的 CI/CD 或手动执行）。
    """
    context.configure(
        url=db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online mode（直接连接数据库执行迁移）
# ---------------------------------------------------------------------------


def do_run_migrations(connection: Connection) -> None:
    """Synchronous migration runner (called via run_sync)."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations with an async engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (async)."""
    asyncio.run(run_async_migrations())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

_is_autogenerate = (
    context.config.cmd_opts is not None
    and getattr(context.config.cmd_opts, "autogenerate", False)
)

if context.is_offline_mode():
    run_migrations_offline()
elif _is_autogenerate:
    # autogenerate：由 alembic 内部调用 context.configure，
    # config.set_main_option 已在上面设置了正确的 URL，
    # target_metadata 也已定义，alembic 使用 sync connection 做 schema diff
    pass
else:
    run_migrations_online()

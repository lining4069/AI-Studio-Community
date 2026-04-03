# Alembic 数据库迁移最佳实践指南

> 基于 FastAPI + SQLAlchemy 2.x + AsyncSession + 环境变量配置的实践总结

---

## 目录

1. [核心配置架构](#1-核心配置架构)
2. [环境变量与配置文件对应关系](#2-环境变量与配置文件对应关系)
3. [日常操作命令](#3-日常操作命令)
4. [新建 Model 到生成迁移](#4-新建-model-到生成迁移)
5. [Raw SQL 表（pg_chunks / pg_sparse_chunks）](#5-raw-sql-表pg_chunks--pg_sparse_chunks)
6. [多环境使用](#6-多环境使用)
7. [CI/CD 中的离线迁移](#7-cicd-中的离线迁移)
8. [常见问题排查](#8-常见问题排查)

---

## 1. 核心配置架构

```
backend/
├── .env.development          # 开发环境
├── .env.test                # 测试环境
├── .env.production          # 生产环境
│
├── alembic.ini              # Alembic 配置文件（URL 占位符，由 env.py 覆盖）
└── alembic/
    ├── env.py               # 关键：读取 Settings → 注入真实 DB URL
    ├── models.py             # 导入所有 ORM 模型（供 autogenerate 检测）
    └── versions/            # 迁移脚本目录
        └── xxxx_initial.py  # 初始迁移
```

### 关键设计原则

| 原则 | 说明 |
|------|------|
| **DB URL 不写在 alembic.ini** | 由 `app.core.settings.Settings` 通过 `.env.${ENVIRONMENT}` 管理，`env.py` 运行时动态注入 |
| **ORM 与 Raw SQL 分离** | 继承 `Base` 的 Model 由 autogenerate 管理；`pg_chunks` 等 Raw SQL 表由手写迁移管理 |
| **与 `get_db()` 共用连接池** | `env.py` 中直接使用 `app.dependencies.infras.database.async_engine`，不重建 engine，保证连接池配置与应用完全一致 |

---

## 2. 环境变量与配置文件对应关系

### `app/core/settings.py` 中的加载逻辑

```python
ENVFILE_PATH = os.path.join(BASE_DIR, f".env.{os.getenv('ENVIRONMENT', 'prod')}")

class Settings(BaseSettings):
    DATABASE_TYPE: str
    DATABASE_USER: str
    DATABASE_PASSWORD: str
    DATABASE_HOST: str
    DATABASE_PORT: int
    DATABASE_NAME: str
    # ... 其他配置

    model_config = SettingsConfigDict(
        env_file=ENVFILE_PATH, env_file_encoding="utf-8", extra="ignore"
    )
```

### `alembic.ini` 中的 URL 配置

```ini
# alembic.ini 中只写占位符（必须有一行），实际 URL 由 env.py 运行时覆盖
sqlalchemy.url = postgresql+asyncpg://placeholder:placeholder@placeholder:5432/placeholder
```

### `alembic/env.py` 中的注入逻辑

```python
from app.core.settings import get_settings

settings = get_settings()  # 读取 .env.${ENVIRONMENT}

if settings.DATABASE_TYPE == "postgresql":
    db_url = (
        f"postgresql+asyncpg://{settings.DATABASE_USER}:{settings.DATABASE_PASSWORD}"
        f"@{settings.DATABASE_HOST}:{settings.DATABASE_PORT}/{settings.DATABASE_NAME}"
    )
# ...
config.set_main_option("sqlalchemy.url", db_url)  # 覆盖 alembic.ini 中的占位符
```

### 三种环境的使用方式

```bash
# 开发环境（自动读取 .env.development）
ENVIRONMENT=development alembic upgrade head

# 测试环境（自动读取 .env.test）
ENVIRONMENT=test alembic upgrade head

# 生产环境（自动读取 .env.production）
ENVIRONMENT=production alembic upgrade head
```

---

## 3. 日常操作命令

> **前提**：确保目标数据库已启动，且 `.env.${ENVIRONMENT}` 中配置正确

### 3.1 初始化（全新数据库）

```bash
# 第一次运行：从空白数据库创建所有表
ENVIRONMENT=development alembic upgrade head
```

### 3.2 生成新的迁移脚本

```bash
# 自动检测 ORM Model 变化，生成迁移脚本（需要 DB 连接，用于对比当前 schema）
ENVIRONMENT=development alembic revision --autogenerate -m "add_xxx_column"

# 手动编写迁移（不连接 DB，只生成空白模板）
ENVIRONMENT=development alembic revision -m "add_xxx_column"
```

### 3.3 应用迁移

```bash
# 应用所有待执行迁移
ENVIRONMENT=development alembic upgrade head

# 迁移到指定版本
ENVIRONMENT=development alembic upgrade <revision_id>

# 回滚一个迁移
ENVIRONMENT=development alembic downgrade -1

# 回滚到初始状态
ENVIRONMENT=development alembic downgrade base
```

### 3.4 查看状态

```bash
# 查看当前数据库版本和所有迁移
ENVIRONMENT=development alembic current
ENVIRONMENT=development alembic history

# 查看待执行的迁移（不实际运行）
ENVIRONMENT=development alembic check
```

### 3.5 生成 SQL 脚本（离线迁移）

```bash
# 生成所有待执行迁移的 SQL 脚本（不连接数据库）
ENVIRONMENT=development alembic upgrade head --sql > migrations.sql

# 生成指定迁移的 SQL
ENVIRONMENT=development alembic upgrade <revision_id> --sql > migration.sql
```

---

## 4. 新建 Model 到生成迁移

### Step 1：定义 Model

在对应的 `models.py` 中添加或修改 Model，**必须继承 `Base`**：

```python
# app/modules/knowledge_base/models.py
from app.common.base import Base

class KbDocument(Base):
    __tablename__ = "kb_documents"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # ...
```

### Step 2：确保 `alembic/models.py` 导入了该 Model

```python
# alembic/models.py
from app.modules.knowledge_base.models import KbDocument  # noqa: F401
```

### Step 3：生成迁移

```bash
# 确保 DB 正在运行
ENVIRONMENT=development alembic revision --autogenerate -m "add_kb_documents_table"
```

### Step 4：检查生成的迁移文件

```python
# alembic/versions/xxxx_add_kb_documents_table.py
def upgrade() -> None:
    op.create_table(
        "kb_documents",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        # ... autogenerate 自动检测的列
    )

def downgrade() -> None:
    op.drop_table("kb_documents")
```

### Step 5：应用迁移

```bash
ENVIRONMENT=development alembic upgrade head
```

---

## 5. Raw SQL 表（pg_chunks / pg_sparse_chunks）

> 这两张表**不继承 Base**，由 `PGSparseStore` / `PGDenseStore` 中的 Raw SQL 管理，不走 ORM。

### 架构说明

```
ORM Model (autogenerate)     Raw SQL Store (手写迁移)
├── User                      ├── pg_chunks (PGDenseStore)
├── LlmModel                  │   embedding: LargeBinary → vector
├── EmbeddingModel             └── pg_sparse_chunks (PGSparseStore)
├── RerankModel                   tokens: Text (jieba 分词结果)
├── KbDocument
└── KbFile
```

### 手写迁移示例

由于不继承 `Base`，需要**手动编写迁移文件**（不用 `--autogenerate`）：

```bash
ENVIRONMENT=development alembic revision -m "add_pg_chunks_table"
```

然后编辑生成的文件，手写 `CREATE TABLE`：

```python
"""add_pg_chunks_table

Revision ID: xxxx
Revises: xxxx_previous
"""
from alembic import op
import sqlalchemy as sa

revision = "xxxx"
down_revision = "xxxx_previous"

def upgrade() -> None:
    # 1. 启用 pgvector extension（需超级用户或已预装）
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # 2. 创建 pg_chunks 表
    op.create_table(
        "pg_chunks",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("document_id", sa.String(length=64), nullable=False),
        sa.Column("kb_id", sa.String(length=64), nullable=False),
        sa.Column("file_id", sa.String(length=64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        # embedding: LargeBinary，应用层 Raw SQL 负责 CAST AS vector
        sa.Column("embedding", sa.LargeBinary(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False, default=dict),
        sa.Index("ix_pg_chunks_kb_id", "kb_id"),
        sa.Index("ix_pg_chunks_file_id", "file_id"),
    )

def downgrade() -> None:
    op.drop_table("pg_chunks")
```

### pgvector 安装（首次部署）

如果 PostgreSQL 实例尚未安装 `pgvector`，需要手动执行一次：

```bash
# 用超级用户连接目标数据库
psql "postgresql://postgres:password@host:5432/ai_studio"

# 在目标数据库内执行
CREATE EXTENSION IF NOT EXISTS vector;

# 验证
\dx vector
```

如果数据库用户**没有超级用户权限**，需要让 DBA 在 PostgreSQL 配置中预先安装：

```ini
# postgresql.conf
shared_preload_libraries = 'vector'
# 然后重启 PostgreSQL 实例
```

---

## 6. 多环境使用

### 6.1 开发环境

```bash
# 启动数据库（Docker 示例）
docker run -d -p 5432:5432 \
  -e POSTGRES_USER=ai_studio_app \
  -e POSTGRES_PASSWORD=Aistudio12345679 \
  -e POSTGRES_DB=ai_studio \
  postgres:16

# 安装 pgvector（只需一次）
psql "postgresql://ai_studio_app:Aistudio12345679@127.0.0.1:5432/ai_studio" \
  -c "CREATE EXTENSION IF NOT EXISTS vector;"

# 应用所有迁移
ENVIRONMENT=development alembic upgrade head

# 修改 Model 后生成新迁移
ENVIRONMENT=development alembic revision --autogenerate -m "add_new_column"
ENVIRONMENT=development alembic upgrade head
```

### 6.2 测试环境

```bash
# 测试数据库通常由测试框架管理（如 docker-compose）
# 确保 .env.test 配置指向测试数据库

ENVIRONMENT=test alembic upgrade head
```

### 6.3 生产环境

```bash
# 生产环境强烈建议：
# 1. 先在 staging 环境测试迁移
# 2. 使用离线模式生成 SQL 脚本，由 DBA 审核后执行

# 生成迁移 SQL 脚本
ENVIRONMENT=production alembic upgrade head --sql > /tmp/migrations.sql

# DBA 审核后，在生产数据库执行
psql "postgresql://user:pass@prod-host:5432/prod_db" -f /tmp/migrations.sql
```

---

## 7. CI/CD 中的离线迁移

推荐在 CI/CD 中使用 **offline 模式**，避免 CI 服务器连接生产数据库：

### 方式 A：生成 SQL 脚本，由 DBA 执行

```bash
# 生成迁移 SQL
ENVIRONMENT=production alembic upgrade head --sql > migrations.sql

# 在 MR/CD 流程中将 migrations.sql 作为 artifact 上传
# 由有权限的人员审核并执行
```

### 方式 B：开发机生成，手动应用

```bash
# 在本地 development 环境生成迁移
ENVIRONMENT=development alembic revision --autogenerate -m "add_xxx"
ENVIRONMENT=development alembic upgrade head   # 验证迁移正确

# 将生成的 .py 文件提交到仓库
git add alembic/versions/xxxx_add_xxx.py
git commit -m "migration: add xxx table"
```

---

## 8. 常见问题排查

### Q1: `alembic revision --autogenerate` 生成空的迁移（只有 `pass`）

**原因**：数据库连接不可达或数据库为空，`autogenerate` 无法检测到现有 schema。

**解决**：
```bash
# 1. 确认数据库正在运行
psql "postgresql://user:pass@host:5432/db" -c "SELECT 1;"

# 2. 如果是新数据库，先运行一次完整迁移（此时 autogenerate 只能看到无变化）
ENVIRONMENT=development alembic upgrade head

# 3. 再修改 Model，重新 autogenerate
# 此时 autogenerate 会对比"数据库当前状态"和"Model 定义"
```

### Q2: `ConnectionRefusedError: [Errno 61] Connect call failed`

**原因**：PostgreSQL 未启动或 `DATABASE_HOST` / `DATABASE_PORT` 配置错误。

**解决**：
```bash
# 检查 .env.development 中的 DATABASE_HOST / PORT
cat .env.development | grep DATABASE

# 确认数据库服务正在运行
pg_isready -h 127.0.0.1 -p 5432
```

### Q3: `target_metadata is None`

**原因**：`env.py` 中的 `target_metadata = None`，所有 Model 未被导入。

**解决**：确保 `alembic/models.py` 中已导入所有 ORM Model，且 `env.py` 顶部有：
```python
from app.modules.users.models import User  # noqa: F401
# ... 其他 models
```

### Q4: `async_engine` 已经在 FastAPI 启动时初始化，alembic 复用会导致冲突吗？

**不会**。`app.dependencies.infras.database.async_engine` 是一个全局单例，使用 `async_engine.dispose()` 关闭 alembic 迁移专用连接，不会影响 FastAPI 路由中的其他连接。

### Q5: 多租户环境下，不同 tenant 的 Raw SQL 表怎么管理？

Raw SQL 表（如 `pg_chunks`）通过 `kb_id` 列做逻辑隔离，不按 tenant 创建独立表。如果需要按 tenant 物理隔离，应在应用层（Store 初始化时）动态创建 schema 或表，Alembic 只负责全局基础表。

### Q6: 如何在 `get_db()` 中开启事务但不希望自动 commit？

`get_db()` 的设计是：路由正常返回 → 自动 commit，路由抛异常 → 自动 rollback。**不要**在正常业务流程中手动控制事务。如需手动控制，使用 `@with_async_db_session` 装饰器：

```python
from app.dependencies.infras.database import with_async_db_session

@with_async_db_session
async def do_something(session):
    session.add(obj)
    # 装饰器自动 commit，异常自动 rollback
```

---

## 附录：核心文件参考

### `alembic/env.py` 关键结构

```python
# 1. 从 Settings 读取真实 DB URL（覆盖 alembic.ini 占位符）
settings = get_settings()
config.set_main_option("sqlalchemy.url", db_url)

# 2. 导入所有 ORM Model（供 autogenerate 检测 schema 变化）
from app.modules.users.models import User  # noqa: F401
# ...

# 3. 复用应用层 async_engine（与 get_db() 共用连接池）
async def run_async_migrations():
    from app.dependencies.infras.database import async_engine
    async with async_engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await async_engine.dispose()

# 4. autogenerate 时不执行实际迁移（避免无 DB 连接时失败）
if _run_with_autogenerate:
    pass  # 只需 target_metadata，不需要连接
elif context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

### `alembic/models.py` 模板

```python
"""
所有使用 SQLAlchemy ORM 的模型必须在此导入。
Raw SQL 表（pg_chunks、pg_sparse_chunks）不在此导入。
"""
from app.common.base import Base
from app.modules.users.models import User  # noqa: F401
from app.modules.llm_model.models import LlmModel  # noqa: F401
from app.modules.embedding_model.models import EmbeddingModel  # noqa: F401
from app.modules.rerank_model.models import RerankModel  # noqa: F401
from app.modules.knowledge_base.models import KbDocument, KbFile  # noqa: F401
```

"""
Alembic autogenerate 模型导入。

所有使用 SQLAlchemy ORM 的模型必须在此导入，
Alembic autogenerate 通过 Base.metadata 检测 schema 变化。

Raw SQL 表（pg_chunks、pg_sparse_chunks）不在此导入，由手写迁移管理。
"""
from app.common.base import Base
from app.modules.users.models import User  # noqa: F401
from app.modules.llm_model.models import LlmModel  # noqa: F401
from app.modules.embedding_model.models import EmbeddingModel  # noqa: F401
from app.modules.rerank_model.models import RerankModel  # noqa: F401
from app.modules.knowledge_base.models import KbDocument, KbFile  # noqa: F401

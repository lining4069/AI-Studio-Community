"""
Alembic migration models import.
All models must be imported here for autogenerate to detect them.
"""

from app.common.base import Base
from app.modules.users.models import User  # noqa: F401
from app.modules.llm_model.models import LlmModel  # noqa: F401
from app.modules.embedding_model.models import EmbeddingModel  # noqa: F401
from app.modules.rerank_model.models import RerankModel  # noqa: F401
from app.modules.knowledge_base.models import KbChunk, KbDocument, KbFile  # noqa: F401

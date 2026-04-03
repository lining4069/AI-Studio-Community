"""
Knowledge Base Module.

Provides:
- Knowledge Base (KB) document CRUD
- Multi-format file upload and management
- File indexing pipeline (load → split → embed → vector DB)
- Hybrid retrieval (dense vector + sparse/BM25)
- Full RAG pipeline with optional LLM generation
"""

from app.modules.knowledge_base.models import (
    KbDocument,
    KbFile,
)
from app.modules.knowledge_base.router import router as kb_router
from app.modules.knowledge_base.schema import (
    KbDocumentCreate,
    KbDocumentResponse,
    KbDocumentUpdate,
    KbFileResponse,
    RAGRequest,
    RAGResponse,
    RetrievalConfig,
    RetrievalRequest,
    RetrievalResponse,
    RetrievalResult,
)
from app.modules.knowledge_base.service import KnowledgeBaseService

__all__ = [
    # Models
    "KbDocument",
    "KbFile",
    # Schemas
    "KbDocumentCreate",
    "KbDocumentUpdate",
    "KbDocumentResponse",
    "KbFileResponse",
    "RetrievalRequest",
    "RetrievalResponse",
    "RAGRequest",
    "RAGResponse",
    "RetrievalConfig",
    "RetrievalResult",
    # Service
    "KnowledgeBaseService",
    # Router
    "kb_router",
]

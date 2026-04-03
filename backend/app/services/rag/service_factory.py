"""
Service Factory - Creates RAG service from Knowledge Base configuration.

Provides factory function to create RAGService instances with proper
embedding/reranker/vector providers based on KB model configuration.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import get_settings
from app.dependencies.infras import get_db
from app.modules.embedding_model.repository import EmbeddingModelRepository
from app.modules.knowledge_base.models import KbDocument
from app.modules.llm_model.repository import LlmModelRepository
from app.modules.rerank_model.repository import RerankModelRepository
from app.services.providers.base import EmbeddingProvider, LLMProvider, RerankerProvider
from app.services.providers.model_factory import (
    create_embedding,
    create_llm,
    create_reranker,
)
from app.services.rag.index_service import RAGIndexService
from app.services.rag.retrieval_service import RAGRetrievalService
from app.services.rag.stores.base import DenseStore, SparseStore
from app.services.rag.stores.chroma_dense import ChromaDenseStore
from app.services.rag.stores.pg_dense import PGDenseStore
from app.services.rag.stores.pg_sparse import PGSparseStore


def _build_dense_store(
    kb: KbDocument,
    embedding_provider: EmbeddingProvider,
    vector_db_type: str,
) -> DenseStore:
    """构建稠密向量存储"""

    if vector_db_type == "chromadb":
        settings = get_settings()
        return ChromaDenseStore(
            embedding_provider=embedding_provider,
            persist_directory=str(settings.CHROMA_PERSIST_DIR),
            collection_name=kb.collection_name,
            user_id=kb.user_id,
        )
    elif vector_db_type == "postgresql":  # postgresql
        return PGDenseStore()
    else:
        raise ValueError(f"Unknown vector_db_type: {vector_db_type}")


def _build_sparse_store(sparse_db_type: str) -> SparseStore:
    """构建稀疏向量存储"""
    if sparse_db_type == "postgresql":
        return PGSparseStore()
    else:
        raise ValueError(f"Unknown sparse_db_type: {sparse_db_type}")


async def create_rag_index_service(
    kb: KbDocument,
    vector_db_type: str = "postgresql",  # "chromadb" | "postgresql"
    sparse_db_type: str = "postgresql",  # "postgresql FTS" | "elasticsearch"
) -> RAGIndexService:
    """
    创建 RAG 索引服务

    Args:
        kb: 知识库配置
        embedding_provider: 嵌入提供者
        db_session: 数据库会话
        vector_db_type: 向量数据库类型，"chromadb" 或 "postgresql"

    Returns:
        RAGIndexService 实例
    """
    session_getter = get_db()
    db_session = await anext(session_getter)
    try:
        # 获取嵌入提供者
        embedding_provider: EmbeddingProvider | None = None
        if not (kb.embedding_model_id and kb.user_id):
            raise ValueError("embedding_model_id and user_id are required")

        repo = EmbeddingModelRepository(db_session)
        embedding_model = await repo.get_by_id(kb.embedding_model_id, kb.user_id)

        if not embedding_model:
            raise ValueError(f"Embedding model {kb.embedding_model_id} not found")
        embedding_provider = create_embedding(embedding_model)

        # 构建稠密向量存储
        dense_store = _build_dense_store(
            kb, embedding_provider, vector_db_type
        )
        # 构建稀疏向量存储
        sparse_store = _build_sparse_store(sparse_db_type)
    finally:
        await db_session.close()

    return RAGIndexService(
        dense_store=dense_store,
        sparse_store=sparse_store,
        embedding_provider=embedding_provider,
    )


async def create_rag_retrieval_service(
    kb: KbDocument,
    llm_model_id: str | None = None,  # LLMMolde uuid
    vector_db_type: str = "postgresql",  # "chromadb" | "postgresql"
    sparse_db_type: str = "postgresql",  # "postgresql FTS" | "elasticsearch"
) -> RAGRetrievalService:
    """
    创建 RAG 检索服务

    Args:
        kb: 知识库配置=>embedding_model_id(必须存在), rerank_model_id(可选)
        llm_model_id: LLM 模型 ID(可选)
        vector_db_type: 向量数据库类型，"chromadb" 或 "postgresql"
        sparse_db_type: 向量数据库类型，"postgresql FTS" 或 "elasticsearch"

    Returns:
        RAGRetrievalService 实例
    """
    session_getter = get_db()
    db_session = await anext(session_getter)
    try:
        # 获取嵌入提供者
        embedding_provider: EmbeddingProvider | None = None
        if not (kb.embedding_model_id and kb.user_id):
            raise ValueError("embedding_model_id and user_id are required")

        repo = EmbeddingModelRepository(db_session)
        embedding_model = await repo.get_by_id(kb.embedding_model_id, kb.user_id)
        if not embedding_model:
            raise ValueError(f"Embedding model {kb.embedding_model_id} not found")
        embedding_provider = create_embedding(embedding_model)

        # 获取重排提供者
        reranker_provider: RerankerProvider | None = None
        if kb.rerank_model_id:
            repo = RerankModelRepository(db_session)
            rerank_model = await repo.get_by_id(kb.rerank_model_id, kb.user_id)

            if not rerank_model:
                raise ValueError(f"Rerank model {kb.rerank_model_id} not found")
            reranker_provider = create_reranker(rerank_model)

        # 获取 LLM 提供者
        llm_provider: LLMProvider | None = None
        if llm_model_id:
            repo = LlmModelRepository(db_session)
            llm_model = await repo.get_by_id(llm_model_id, kb.user_id)

            if not llm_model:
                raise ValueError(f"LLM model {llm_model_id} not found")
            llm_provider = create_llm(llm_model)

        # 构建稠密向量存储
        dense_store = _build_dense_store(
            kb, embedding_provider, vector_db_type
        )

        # 构建稀疏向量存储
        sparse_store = _build_sparse_store(sparse_db_type)
    finally:
        await db_session.close()

    return RAGRetrievalService(
        dense_store=dense_store,
        sparse_store=sparse_store,
        embedding_provider=embedding_provider,
        reranker_provider=reranker_provider,
        llm_provider=llm_provider,
    )

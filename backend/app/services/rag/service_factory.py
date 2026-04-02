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
from app.modules.rerank_model.repository import RerankModelRepository
from app.services.providers.base import EmbeddingProvider, LLMProvider, RerankerProvider
from app.services.providers.model_factory import create_embedding, create_reranker
from app.services.rag.rag_service import RAGService
from app.services.vectordb.base import VectorDBProvider
from app.services.vectordb.chroma_service import ChromaDBProvider
from app.services.rag.stores.base import DenseStore
from app.services.rag.stores.chroma_dense import ChromaDenseStore
from app.services.rag.stores.pg_dense import PGDenseStore
from app.services.rag.stores.pg_sparse import PGSparseStore
from app.services.rag.index_service import RAGIndexService
from app.services.rag.retrieval_service import RAGRetrievalService


def _build_vector_provider(
    embedding_provider: EmbeddingProvider,
) -> VectorDBProvider:
    """Build a VectorDBProvider based on settings."""
    settings = get_settings()
    engine = settings.VECTOR_DB_ENGINE.lower()

    if engine == "chromadb":
        return ChromaDBProvider(
            embedding_provider=embedding_provider,
            persist_directory=str(settings.CHROMA_PERSIST_DIR),
        )
    elif engine == "milvus":
        from app.services.vectordb.milvus_service import MilvusProvider

        return MilvusProvider(
            embedding_provider=embedding_provider,
            host=settings.MILVUS_HOST,
            port=settings.MILVUS_PORT,
            user=settings.MILVUS_USER,
            password=settings.MILVUS_PASSWORD,
        )
    else:
        raise ValueError(f"Unknown VECTOR_DB_ENGINE: {engine}")


async def get_rag_service(
    kb: KbDocument,
    llm_provider: LLMProvider | None = None,
) -> RAGService:
    """
    Create a RAGService instance for a Knowledge Base.

    Args:
        kb: Knowledge Base document with model configuration

    Returns:
        RAGService instance configured with the KB's embedding/reranker models
    """
    session_getter = get_db()
    session = await anext(session_getter)
    try:
        # Get embedding provider
        embedding_provider: EmbeddingProvider | None = None
        if kb.embedding_model_id:
            repo = EmbeddingModelRepository(session)
            embedding_model = await repo.get_by_id(kb.embedding_model_id, kb.user_id)
            if embedding_model:
                embedding_provider = create_embedding(embedding_model)
            else:
                raise ValueError(f"Embedding model {kb.embedding_model_id} not found")

        if not embedding_provider:
            raise ValueError("Embedding provider is required for RAGService")

        # Get reranker provider
        reranker_provider: RerankerProvider | None = None
        if kb.rerank_model_id:
            repo = RerankModelRepository(session)
            rerank_model = await repo.get_by_id(kb.rerank_model_id, kb.user_id)
            if rerank_model:
                reranker_provider = create_reranker(rerank_model)

        # Build vector provider
        vector_provider = _build_vector_provider(embedding_provider)

        return RAGService(
            vector_provider=vector_provider,
            embedding_provider=embedding_provider,
            reranker_provider=reranker_provider,
            llm_provider=llm_provider,
        )
    finally:
        await session.close()


async def create_rag_index_service(
    kb: KbDocument,
    embedding_provider: EmbeddingProvider,
    db_session: AsyncSession,
    vector_db_type: str = "chromadb",  # "chromadb" | "postgresql"
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
    if vector_db_type == "chromadb":
        settings = get_settings()
        dense_store: DenseStore = ChromaDenseStore(
            embedding_provider=embedding_provider,
            persist_directory=str(settings.CHROMA_PERSIST_DIR),
            collection_name=kb.collection_name,
            user_id=kb.user_id,
        )
    else:  # postgresql
        dense_store = PGDenseStore(
            db_session=db_session,
            embedding_provider=embedding_provider,
        )

    sparse_store = PGSparseStore(db_session=db_session)

    return RAGIndexService(
        dense_store=dense_store,
        sparse_store=sparse_store,
        embedding_provider=embedding_provider,
    )


async def create_rag_retrieval_service(
    kb: KbDocument,
    embedding_provider: EmbeddingProvider,
    db_session: AsyncSession,
    reranker_provider: RerankerProvider | None = None,
    llm_provider: LLMProvider | None = None,
    vector_db_type: str = "chromadb",
) -> RAGRetrievalService:
    """
    创建 RAG 检索服务

    Args:
        kb: 知识库配置
        embedding_provider: 嵌入提供者
        db_session: 数据库会话
        reranker_provider: 重排提供者
        llm_provider: LLM 提供者
        vector_db_type: 向量数据库类型

    Returns:
        RAGRetrievalService 实例
    """
    if vector_db_type == "chromadb":
        settings = get_settings()
        dense_store: DenseStore = ChromaDenseStore(
            embedding_provider=embedding_provider,
            persist_directory=str(settings.CHROMA_PERSIST_DIR),
            collection_name=kb.collection_name,
            user_id=kb.user_id,
        )
    else:
        dense_store = PGDenseStore(
            db_session=db_session,
            embedding_provider=embedding_provider,
        )

    sparse_store = PGSparseStore(db_session=db_session)

    return RAGRetrievalService(
        dense_store=dense_store,
        sparse_store=sparse_store,
        embedding_provider=embedding_provider,
        reranker_provider=reranker_provider,
        llm_provider=llm_provider,
    )

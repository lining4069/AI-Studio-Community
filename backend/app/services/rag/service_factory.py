"""
Service Factory - Creates RAG service from Knowledge Base configuration.

Provides factory function to create RAGService instances with proper
embedding/reranker/vector providers based on KB model configuration.
"""

from app.core.settings import get_settings
from app.dependencies.infras import get_db
from app.modules.embedding_model.repository import EmbeddingModelRepository
from app.modules.knowledge_base.models import KbDocument
from app.modules.rerank_model.repository import RerankModelRepository
from app.services.factory.model_factory import create_embedding, create_reranker
from app.services.providers.base import EmbeddingProvider, LLMProvider, RerankerProvider
from app.services.rag.rag_service import RAGService
from app.services.vectordb.base import VectorDBProvider
from app.services.vectordb.chroma_service import ChromaDBProvider


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
            embedding_provider=embedding_provider,
            reranker_provider=reranker_provider,
            llm_provider=llm_provider,
            vector_provider=vector_provider,
        )
    finally:
        await session.close()

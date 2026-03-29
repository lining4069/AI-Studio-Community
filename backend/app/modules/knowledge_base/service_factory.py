"""
Service Factory - Creates RAG service from Knowledge Base configuration.

Provides factory function to create RAGService instances with proper
embedding/reranker providers based on KB model configuration.
"""

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.embedding_model.repository import EmbeddingModelRepository
from app.modules.knowledge_base.models import KbDocument
from app.modules.rerank_model.repository import RerankModelRepository
from app.services.factory.model_factory import create_embedding, create_reranker
from app.services.rag.rag_service import RAGService


async def get_rag_service(kb: KbDocument, db: AsyncSession | None = None) -> RAGService:
    """
    Create or get a RAGService instance for a Knowledge Base.

    Args:
        kb: Knowledge Base document with model configuration
        db: Optional database session for looking up models

    Returns:
        RAGService instance configured with the KB's embedding/reranker models
    """
    # Get embedding provider
    embedding_provider = None
    if kb.embedding_model_id and db:
        repo = EmbeddingModelRepository(db)
        embedding_model = await repo.get_by_id(kb.embedding_model_id, kb.user_id)
        if embedding_model:
            embedding_provider = create_embedding(embedding_model)
            logger.info(f"Using embedding model: {embedding_model.name}")
        else:
            logger.warning(f"Embedding model {kb.embedding_model_id} not found")
    elif kb.embedding_model_id:
        logger.warning(
            f"No db session provided, cannot load embedding model {kb.embedding_model_id}"
        )
    else:
        logger.warning(f"No embedding model configured for KB {kb.id}")

    # Get reranker provider
    reranker_provider = None
    if kb.rerank_model_id and db:
        repo = RerankModelRepository(db)
        rerank_model = await repo.get_by_id(kb.rerank_model_id, kb.user_id)
        if rerank_model:
            reranker_provider = create_reranker(rerank_model)
            logger.info(f"Using reranker model: {rerank_model.name}")
        else:
            logger.warning(f"Reranker model {kb.rerank_model_id} not found")

    return RAGService(
        embedding_provider=embedding_provider,
        reranker_provider=reranker_provider,
    )

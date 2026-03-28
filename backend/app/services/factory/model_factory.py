"""
Model Factory - Factory functions for creating model provider instances.

This module follows the factory pattern with caching to avoid recreating
expensive model instances. It creates the appropriate provider based on
model configuration and caches them for reuse.

Reference: PAI-RAG backend/service/factory/model_factory.py
"""
from typing import Optional

from loguru import logger

from app.modules.llm_model.models import LlmModel
from app.modules.embedding_model.models import EmbeddingModel, EmbeddingType
from app.modules.rerank_model.models import RerankModel, RerankType
from app.services.providers.base import LLMProvider, EmbeddingProvider, RerankerProvider
from app.services.providers.dashscope import (
    DashScopeLLMProvider,
    DashScopeEmbeddingProvider,
    DashScopeRerankerProvider,
)
from app.services.providers.openai_compatible import (
    OpenAICompatibleLLMProvider,
    OpenAICompatibleEmbeddingProvider,
    CohereRerankerProvider,
)
from app.services.providers.huggingface import HuggingFaceEmbeddingProvider
from app.utils.lru_cache import LruCache
from app.utils.encrypt_utils import decrypt_api_key

# ============================================================================
# LRU Caches for Model Instances
# ============================================================================

llm_cache = LruCache(max_size=20)  # Cache up to 20 LLM instances
embedding_cache = LruCache(max_size=10)  # Cache up to 10 Embedding instances
reranker_cache = LruCache(max_size=10)  # Cache up to 10 Reranker instances


# ============================================================================
# Cache Key Generators
# ============================================================================


def _llm_cache_key(model: LlmModel) -> str:
    """Generate cache key for LLM model"""
    decrypted_key = decrypt_api_key(model.encrypted_api_key or "")
    return (
        f"llm_{model.provider}_{model.model_name}_"
        f"{decrypted_key}_{model.temperature}"
    )


def _embedding_cache_key(model: EmbeddingModel) -> str:
    """Generate cache key for Embedding model"""
    if model.type == EmbeddingType.LOCAL:
        return f"embed_local_{model.local_model_path or model.model_name}"
    decrypted_key = decrypt_api_key(model.encrypted_api_key or "")
    return (
        f"embed_{model.endpoint or ''}_{model.model_name}_"
        f"{model.dimension}_{decrypted_key}"
    )


def _reranker_cache_key(model: RerankModel) -> str:
    """Generate cache key for Reranker model"""
    decrypted_key = decrypt_api_key(model.encrypted_api_key or "")
    return f"rerank_{model.type}_{model.model_name}_{model.base_url}_{decrypted_key}"


# ============================================================================
# LLM Factory
# ============================================================================


def create_llm(model: LlmModel) -> LLMProvider:
    """
    Create or get cached LLM provider instance.

    Args:
        model: LLM model configuration from database

    Returns:
        LLMProvider instance ready for inference
    """
    cache_key = _llm_cache_key(model)

    cached = llm_cache.get(cache_key)
    if cached:
        logger.info(f"Using cached LLM provider: {model.name}")
        return cached

    logger.info(f"Creating new LLM provider: {model.name} ({model.provider})")

    # Get decrypted API key
    api_key = decrypt_api_key(model.encrypted_api_key or "")

    # Create provider based on type
    if model.provider == "dashscope":
        provider = DashScopeLLMProvider(
            api_key=api_key,
            model=model.model_name,
            temperature=model.temperature,
            max_tokens=model.max_tokens,
        )
    elif model.provider == "openai_compatible":
        provider = OpenAICompatibleLLMProvider(
            api_key=api_key,
            base_url=model.base_url or "",
            model=model.model_name,
            temperature=model.temperature,
            max_tokens=model.max_tokens,
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {model.provider}")

    llm_cache.put(cache_key, provider)
    return provider


# ============================================================================
# Embedding Factory
# ============================================================================


def create_embedding(model: EmbeddingModel) -> EmbeddingProvider:
    """
    Create or get cached Embedding provider instance.

    Args:
        model: Embedding model configuration from database

    Returns:
        EmbeddingProvider instance ready for inference
    """
    cache_key = _embedding_cache_key(model)

    cached = embedding_cache.get(cache_key)
    if cached:
        logger.info(f"Using cached Embedding provider: {model.name}")
        return cached

    logger.info(f"Creating new Embedding provider: {model.name} ({model.type})")

    # Create provider based on type
    if model.type == EmbeddingType.LOCAL:
        provider = HuggingFaceEmbeddingProvider(
            model_name=model.local_model_path or model.model_name or "",
            batch_size=model.batch_size,
        )
    elif model.type == EmbeddingType.OPENAI_COMPATIBLE:
        api_key = decrypt_api_key(model.encrypted_api_key or "")
        provider = OpenAICompatibleEmbeddingProvider(
            api_key=api_key,
            endpoint=model.endpoint or "",
            model=model.model_name or "",
            dimension=model.dimension,
            batch_size=model.batch_size,
        )
    else:
        raise ValueError(f"Unsupported Embedding type: {model.type}")

    embedding_cache.put(cache_key, provider)
    return provider


# ============================================================================
# Reranker Factory
# ============================================================================


def create_reranker(model: RerankModel) -> RerankerProvider:
    """
    Create or get cached Reranker provider instance.

    Args:
        model: Reranker model configuration from database

    Returns:
        RerankerProvider instance ready for inference
    """
    cache_key = _reranker_cache_key(model)

    cached = reranker_cache.get(cache_key)
    if cached:
        logger.info(f"Using cached Reranker provider: {model.name}")
        return cached

    logger.info(f"Creating new Reranker provider: {model.name} ({model.type})")

    # Get decrypted API key
    api_key = decrypt_api_key(model.encrypted_api_key or "")

    # Create provider based on type
    if model.type == RerankType.DASHSCOPE:
        provider = DashScopeRerankerProvider(
            api_key=api_key,
            model=model.model_name or "qwen3-rerank",
            base_url=model.base_url or "",
        )
    elif model.type == RerankType.OPENAI_COMPATIBLE:
        provider = CohereRerankerProvider(
            api_key=api_key,
            base_url=model.base_url or "",
            model=model.model_name,
            top_n=model.top_n,
        )
    else:
        raise ValueError(f"Unsupported Reranker type: {model.type}")

    reranker_cache.put(cache_key, provider)
    return provider


# ============================================================================
# Cache Management
# ============================================================================


def clear_llm_cache() -> None:
    """Clear all cached LLM instances"""
    global llm_cache
    llm_cache.clear()


def clear_embedding_cache() -> None:
    """Clear all cached Embedding instances"""
    global embedding_cache
    embedding_cache.clear()


def clear_reranker_cache() -> None:
    """Clear all cached Reranker instances"""
    global reranker_cache
    reranker_cache.clear()


def clear_all_caches() -> None:
    """Clear all model caches"""
    clear_llm_cache()
    clear_embedding_cache()
    clear_reranker_cache()
    logger.info("All model caches cleared")

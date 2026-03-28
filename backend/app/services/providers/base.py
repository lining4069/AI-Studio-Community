"""
Base interfaces for Model Providers.

These abstract base classes define the contract that all model providers
must implement, enabling the factory pattern to create providers uniformly.
"""
from abc import ABC, abstractmethod
from typing import List, AsyncGenerator, Any, Dict


class LLMProvider(ABC):
    """
    Abstract interface for LLM (Large Language Model) providers.

    All LLM providers (OpenAI, DashScope, Cohere, etc.) must implement this interface.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name identifier"""
        pass

    @abstractmethod
    async def astream(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]] | None = None,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat completion responses.

        Args:
            messages: List of message dicts with 'role' and 'content'
            tools: Optional list of tool definitions in OpenAI format

        Yields:
            String chunks of the response
        """
        pass

    @abstractmethod
    async def achat(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]] | None = None,
        **kwargs,
    ) -> str:
        """
        Non-streaming chat completion.

        Args:
            messages: List of message dicts with 'role' and 'content'
            tools: Optional list of tool definitions

        Returns:
            Complete response string
        """
        pass


class EmbeddingProvider(ABC):
    """
    Abstract interface for Embedding providers.

    All embedding providers (OpenAI, DashScope, HuggingFace, etc.) must implement this interface.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name identifier"""
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the embedding dimension"""
        pass

    @abstractmethod
    async def aembed(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a batch of texts.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors
        """
        pass

    @abstractmethod
    async def aembed_query(self, query: str) -> List[float]:
        """
        Generate embedding for a single query.

        Args:
            query: Query string to embed

        Returns:
            Query embedding vector
        """
        pass


class RerankerProvider(ABC):
    """
    Abstract interface for Reranker providers.

    All reranker providers (Cohere, DashScope, Jina, etc.) must implement this interface.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name identifier"""
        pass

    @abstractmethod
    async def arerank(
        self,
        query: str,
        documents: List[str],
        top_n: int | None = None,
    ) -> List[Dict[str, Any]]:
        """
        Rerank documents by relevance to query.

        Args:
            query: Query string
            documents: List of document strings to rerank
            top_n: Number of top results to return (None = all)

        Returns:
            List of dicts with 'index', 'score', and 'document' keys
        """
        pass

"""
VectorDB Provider Base Classes.

Abstract interfaces for vector database implementations, enabling
swap between ChromaDB, Milvus, and other vector stores.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from app.services.providers.base import EmbeddingProvider


class VectorStore(Protocol):
    """
    Protocol defining the vector store operations interface.

    Each collection/namespace in a vector DB implements this protocol.
    """

    @property
    def collection(self) -> Any:
        """Access to the underlying collection (ChromaDB-specific)."""
        ...

    def add_texts(
        self,
        texts: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict] | None = None,
        ids: list[str] | None = None,
    ) -> list[str]:
        """Add documents to the store."""
        ...

    def delete(self, ids: list[str]) -> None:
        """Delete documents by IDs."""
        ...

    def delete_by_file_id(self, file_id: str) -> int:
        """Delete all documents for a specific file. Returns count deleted."""
        ...

    def delete_collection(self) -> None:
        """Delete the entire collection."""
        ...

    def count(self) -> int:
        """Get collection count."""
        ...

    def peek(self, limit: int = 10) -> dict:
        """Peek at first N documents."""
        ...

    def similarity_search(
        self,
        query: str,
        k: int = 5,
        filter_metadata: dict | None = None,
    ) -> list[tuple[str, str, float]]:
        """
        Dense vector similarity search.

        Returns:
            List of (id, text, score) tuples
        """
        ...

    def hybrid_search(
        self,
        query: str,
        k: int = 5,
        vector_weight: float = 0.7,
        filter_metadata: dict | None = None,
    ) -> list[tuple[str, str, float]]:
        """
        Hybrid search (dense + sparse/BM25).

        Returns:
            List of (id, text, score) tuples
        """
        ...


class VectorDBProvider(ABC):
    """
    Abstract base class for vector database providers.

    Acts as a factory for VectorStore instances, one per collection.
    Subclasses implement the same interface for different backends
    (ChromaDB, Milvus, etc.).
    """

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        persist_directory: str | None = None,
    ):
        """
        Initialize the vector DB provider.

        Args:
            embedding_provider: Provider for generating text embeddings
            persist_directory: Base directory for persistent storage (backend-specific)
        """
        self.embedding_provider = embedding_provider
        self.persist_directory = persist_directory

    @abstractmethod
    def get_vector_store(
        self,
        collection_name: str,
        user_id: int,
    ) -> VectorStore:
        """
        Get or create a vector store for a collection.

        Args:
            collection_name: Name of the collection (typically kb_id)
            user_id: User ID for isolation

        Returns:
            VectorStore instance for the collection
        """
        ...

    @property
    @abstractmethod
    def engine_name(self) -> str:
        """Return the engine name (e.g., 'chromadb', 'milvus')."""
        ...

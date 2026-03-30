"""
ChromaDB Vector Store Integration.

Provides ChromaDB-backed vector storage with hybrid search (dense + BM25).
Implements VectorDBProvider for the chromadb engine.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import chromadb
from chromadb.config import Settings
from loguru import logger

from app.services.providers.base import EmbeddingProvider
from app.services.vectordb.base import VectorDBProvider, VectorStore

if TYPE_CHECKING:
    pass

# ChromaDB client singleton per persist_directory (fix: was global singleton ignoring dir)
_chroma_clients: dict[str, chromadb.PersistentClient] = {}


def _get_chroma_client(persist_directory: str) -> chromadb.PersistentClient:
    """
    Get or create ChromaDB client for a specific persist directory.

    Uses a per-directory singleton so different users get different clients.
    """
    if persist_directory not in _chroma_clients:
        _chroma_clients[persist_directory] = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(anonymized_telemetry=False),
        )
        logger.info(f"Created ChromaDB client for: {persist_directory}")
    return _chroma_clients[persist_directory]


class ChromaCollection:
    """
    ChromaDB collection wrapper for vector operations.

    Supports:
    - Dense vector search (embedding)
    - Sparse/Bm25 search (keyword)
    - Hybrid search with configurable weights
    """

    def __init__(
        self,
        collection_name: str,
        embedding_function: Any,  # Callable that returns embeddings
        persist_directory: str,
    ):
        self.collection_name = collection_name
        self.embedding_function = embedding_function
        self.persist_directory = persist_directory
        self._client = _get_chroma_client(persist_directory)
        self._collection = None

        self._get_or_create_collection()

    def _get_or_create_collection(self) -> None:
        """Create or get the ChromaDB collection"""
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    @property
    def collection(self):
        """Lazy load collection"""
        if self._collection is None:
            self._get_or_create_collection()
        return self._collection

    def add(
        self,
        texts: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict] | None = None,
        ids: list[str] | None = None,
    ) -> list[str]:
        """Add documents to the collection."""
        if ids is None:
            ids = [str(uuid.uuid4()) for _ in texts]
        if metadatas is None:
            metadatas = [{} for _ in texts]
        self.collection.add(
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids,
        )
        return ids

    def delete(self, ids: list[str]) -> None:
        """Delete documents by IDs"""
        self.collection.delete(ids=ids)

    def delete_where(self, where_filter: dict) -> int:
        """Delete documents matching a metadata filter."""
        count_before = self.count()
        self.collection.delete(where=where_filter)
        count_after = self.count()
        return count_before - count_after

    def delete_by_file_id(self, file_id: str) -> int:
        """Delete all documents for a specific file."""
        return self.delete_where({"file_id": file_id})

    def delete_collection(self) -> None:
        """Delete the entire collection"""
        self._client.delete_collection(name=self.collection_name)
        self._collection = None

    def query_dense(
        self,
        query_embedding: list[float],
        n_results: int = 10,
        where_filter: dict | None = None,
        where_document_filter: dict | None = None,
    ) -> dict:
        """Dense vector search."""
        return self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where_filter,
            where_document=where_document_filter,
        )

    def query_sparse(
        self,
        query_texts: list[str],
        n_results: int = 10,
        where_filter: dict | None = None,
    ) -> dict:
        """Sparse/BM25 keyword search."""
        try:
            return self.collection.query(
                query_texts=query_texts,
                n_results=n_results,
                where=where_filter,
            )
        except Exception as e:
            logger.warning(f"Sparse search not supported: {e}. Falling back to dense.")
            return self.query_dense(
                query_embedding=self.embedding_function([query_texts[0]])[0],
                n_results=n_results,
                where_filter=where_filter,
            )

    def query_hybrid(
        self,
        query_embedding: list[float],
        query_text: str,
        n_results: int = 10,
        vector_weight: float = 0.7,
        where_filter: dict | None = None,
    ) -> tuple[list[str], list[str], list[float]]:
        """Hybrid search combining dense and sparse results using RRF."""
        dense_results = self.query_dense(query_embedding, n_results * 2, where_filter)
        sparse_results = self.query_sparse([query_text], n_results * 2, where_filter)
        fused = self._rrf_fusion(
            dense_results, sparse_results, vector_weight, n_results
        )
        return fused["ids"], fused["documents"], fused["distances"]

    def _rrf_fusion(
        self,
        dense_results: dict,
        sparse_results: dict,
        vector_weight: float,
        k: int = 60,
        limit: int = 10,
    ) -> dict:
        """Reciprocal Rank Fusion to combine dense and sparse results."""
        dense_weight = vector_weight
        sparse_weight = 1 - vector_weight

        scores: dict[str, float] = {}

        if dense_results.get("ids") and len(dense_results["ids"]) > 0:
            for rank, (doc_id, dist) in enumerate(
                zip(dense_results["ids"][0], dense_results["distances"][0], strict=True)
            ):
                similarity = 1 - dist
                scores[doc_id] = (
                    scores.get(doc_id, 0)
                    + dense_weight * (1 / (k + rank + 1)) * similarity
                )

        if sparse_results.get("ids") and len(sparse_results["ids"]) > 0:
            for rank, (doc_id, dist) in enumerate(
                zip(
                    sparse_results["ids"][0],
                    sparse_results["distances"][0],
                    strict=True,
                )
            ):
                similarity = 1 - dist
                scores[doc_id] = (
                    scores.get(doc_id, 0)
                    + sparse_weight * (1 / (k + rank + 1)) * similarity
                )

        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)[
            :limit
        ]

        id_to_doc = {}
        id_to_dist = {}

        for ids_list, docs_list, dists_list in [
            (
                dense_results.get("ids", [[]])[0],
                dense_results.get("documents", [[]])[0],
                dense_results.get("distances", [[]])[0],
            ),
            (
                sparse_results.get("ids", [[]])[0],
                sparse_results.get("documents", [[]])[0],
                sparse_results.get("distances", [[]])[0],
            ),
        ]:
            for doc_id, doc, dist in zip(ids_list, docs_list, dists_list, strict=True):
                id_to_doc[doc_id] = doc
                id_to_dist[doc_id] = dist

        return {
            "ids": sorted_ids,
            "documents": [id_to_doc.get(uid, "") for uid in sorted_ids],
            "distances": [1 - scores[uid] for uid in sorted_ids],
        }

    def count(self) -> int:
        """Get collection count"""
        return self.collection.count()

    def peek(self, limit: int = 10) -> dict:
        """Peek at first N documents"""
        return self.collection.peek(limit=limit)


class ChromaVectorStore:
    """
    ChromaDB vector store wrapper implementing VectorStore protocol.

    Provides async-friendly interface for vector operations.
    """

    def __init__(
        self,
        collection_name: str,
        embedding_provider: EmbeddingProvider,
        persist_directory: str,
    ):
        self.collection_name = collection_name
        self.embedding_provider = embedding_provider
        self.persist_directory = persist_directory
        self._collection: ChromaCollection | None = None

    @property
    def collection(self) -> ChromaCollection:
        """Expose underlying ChromaCollection for provider-specific access."""
        if self._collection is None:
            self._collection = ChromaCollection(
                collection_name=self.collection_name,
                embedding_function=self._get_embeddings,
                persist_directory=self.persist_directory,
            )
        return self._collection

    def _get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Sync wrapper for embedding provider."""
        import asyncio
        import concurrent.futures

        try:
            asyncio.get_running_loop()

            def _sync_embed():
                return asyncio.run(self.embedding_provider.aembed(texts))

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(_sync_embed)
                return future.result()
        except RuntimeError:
            return asyncio.run(self.embedding_provider.aembed(texts))

    def add_texts(
        self,
        texts: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict] | None = None,
        ids: list[str] | None = None,
    ) -> list[str]:
        """Add texts with embeddings."""
        return self.collection.add(
            texts=texts,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids,
        )

    def delete(self, ids: list[str]) -> None:
        """Delete documents by IDs"""
        self.collection.delete(ids=ids)

    def delete_by_file_id(self, file_id: str) -> int:
        """Delete all documents for a specific file."""
        return self.collection.delete_by_file_id(file_id)

    def delete_collection(self) -> None:
        """Delete the entire collection"""
        self.collection.delete_collection()

    def count(self) -> int:
        """Get collection count"""
        return self.collection.count()

    def peek(self, limit: int = 10) -> dict:
        """Peek at first N documents"""
        return self.collection.peek(limit=limit)

    def similarity_search(
        self,
        query: str,
        k: int = 5,
        filter_metadata: dict | None = None,
    ) -> list[tuple[str, str, float]]:
        """Dense similarity search."""
        query_embedding = self._get_embeddings([query])[0]
        results = self.collection.query_dense(
            query_embedding=query_embedding,
            n_results=k,
            where_filter=filter_metadata,
        )
        return list(
            zip(
                results["ids"][0],
                results["documents"][0],
                [1 - d for d in results["distances"][0]],
                strict=True,
            )
        )

    def hybrid_search(
        self,
        query: str,
        k: int = 5,
        vector_weight: float = 0.7,
        filter_metadata: dict | None = None,
    ) -> list[tuple[str, str, float]]:
        """Hybrid search (dense + sparse/BM25)."""
        query_embedding = self._get_embeddings([query])[0]
        ids, docs, distances = self.collection.query_hybrid(
            query_embedding=query_embedding,
            query_text=query,
            n_results=k,
            vector_weight=vector_weight,
            where_filter=filter_metadata,
        )
        return list(zip(ids, docs, [1 - d for d in distances], strict=True))

    def delete_by_kb_id(self, kb_id: str) -> int:
        """Delete all documents for a knowledge base."""
        return self.collection.delete_where({"kb_id": kb_id})


class ChromaDBProvider(VectorDBProvider):
    """
    ChromaDB vector database provider.

    User isolation: each user gets a separate persist_directory:
        {base_persist_dir}/{user_id}/
    """

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        persist_directory: str = "./data/chroma",
    ):
        super().__init__(embedding_provider=embedding_provider)
        self._base_persist_dir = persist_directory

    def _user_dir(self, user_id: int) -> str:
        """Get the persist directory for a specific user."""
        import os

        user_dir = os.path.join(self._base_persist_dir, str(user_id))
        os.makedirs(user_dir, exist_ok=True)
        return user_dir

    def get_vector_store(
        self,
        collection_name: str,
        user_id: int,
    ) -> VectorStore:
        """
        Get a ChromaVectorStore for a user's collection.

        Each user gets an isolated persist directory.
        """
        user_persist_dir = self._user_dir(user_id)
        return ChromaVectorStore(
            collection_name=collection_name,
            embedding_provider=self.embedding_provider,
            persist_directory=user_persist_dir,
        )

    @property
    def engine_name(self) -> str:
        return "chromadb"

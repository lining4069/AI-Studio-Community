"""
ChromaDB Vector Store Integration.

Provides ChromaDB-backed vector storage with hybrid search (dense + BM25).
"""
import uuid

import chromadb
from chromadb.config import Settings
from loguru import logger

from app.services.providers.base import EmbeddingProvider

# ChromaDB client singleton
_chroma_client: chromadb.PersistentClient | None = None
_chroma_server_client: chromadb.HttpClient | None = None


def get_chroma_client(
    persist_directory: str = "./data/chroma",
    host: str = "localhost",
    port: int = 8000,
    use_http: bool = False,
) -> chromadb.ClientAPI:
    """
    Get or create ChromaDB client.

    Args:
        persist_directory: Directory for persistent storage
        host: ChromaDB server host
        port: ChromaDB server port
        use_http: Whether to use HTTP client (for server mode)

    Returns:
        ChromaDB client
    """
    global _chroma_client, _chroma_server_client

    if use_http:
        if _chroma_server_client is None:
            _chroma_server_client = chromadb.HttpClient(host=host, port=port)
        return _chroma_server_client
    else:
        if _chroma_client is None:
            _chroma_client = chromadb.PersistentClient(
                path=persist_directory,
                settings=Settings(anonymized_telemetry=False),
            )
        return _chroma_client


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
        embedding_function,  # Callable that returns embeddings
        persist_directory: str = "./data/chroma",
        get_or_create: bool = True,
    ):
        self.collection_name = collection_name
        self.embedding_function = embedding_function
        self.persist_directory = persist_directory
        self._client = get_chroma_client(persist_directory=persist_directory)
        self._collection = None

        if get_or_create:
            self._get_or_create_collection()

    def _get_or_create_collection(self):
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
        """
        Add documents to the collection.

        Args:
            texts: Document texts
            embeddings: Dense vectors
            metadatas: Optional metadata per document
            ids: Optional IDs (generated if not provided)

        Returns:
            List of document IDs
        """
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
        """
        Delete documents matching a metadata filter.

        Args:
            where_filter: ChromaDB where clause (e.g., {"kb_id": "xxx"})

        Returns:
            Number of documents deleted (approximate)
        """
        # Get count before deletion for reporting
        count_before = self.count()

        self.collection.delete(where=where_filter)

        # Return approximate count (ChromaDB doesn't return delete count)
        count_after = self.count()
        return count_before - count_after

    def delete_by_file_id(self, file_id: str) -> int:
        """
        Delete all documents for a specific file.

        Args:
            file_id: File ID

        Returns:
            Number of documents deleted
        """
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
        """
        Dense vector search.

        Args:
            query_embedding: Query vector
            n_results: Number of results
            where_filter: Metadata filter (ChromaDB where clause)
            where_document_filter: Document content filter

        Returns:
            ChromaDB query results
        """
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
        """
        Sparse/BM25 keyword search.

        Uses ChromaDB's built-in BM25 functionality.
        Note: Requires ChromaDB >= 0.4.22 with sparse vector support.

        Args:
            query_texts: Query texts
            n_results: Number of results
            where_filter: Metadata filter

        Returns:
            ChromaDB query results
        """
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
        """
        Hybrid search combining dense and sparse results.

        Uses Reciprocal Rank Fusion (RRF) to combine results.

        Args:
            query_embedding: Dense query vector
            query_text: Query text for BM25
            n_results: Number of results
            vector_weight: Weight for dense results (1 - vector_weight for sparse)
            where_filter: Metadata filter

        Returns:
            Tuple of (ids, documents, scores)
        """
        # Get dense results
        dense_results = self.query_dense(
            query_embedding, n_results * 2, where_filter
        )

        # Get sparse results
        sparse_results = self.query_sparse(
            [query_text], n_results * 2, where_filter
        )

        # RRF fusion
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
        """
        Reciprocal Rank Fusion to combine dense and sparse results.

        Args:
            dense_results: Results from dense search
            sparse_results: Results from sparse search
            vector_weight: Weight for dense (sparse gets 1 - vector_weight)
            k: RRF constant (typically 60)
            limit: Number of final results

        Returns:
            Fused results dict with ids, documents, distances
        """
        dense_weight = vector_weight
        sparse_weight = 1 - vector_weight

        # Build score maps
        scores: dict[str, float] = {}

        # Dense scores
        if dense_results.get("ids") and len(dense_results["ids"]) > 0:
            for rank, (doc_id, dist) in enumerate(
                zip(dense_results["ids"][0], dense_results["distances"][0])
            ):
                # Convert distance to similarity (ChromaDB uses cosine distance)
                similarity = 1 - dist
                scores[doc_id] = scores.get(doc_id, 0) + dense_weight * (1 / (k + rank + 1)) * similarity

        # Sparse scores
        if sparse_results.get("ids") and len(sparse_results["ids"]) > 0:
            for rank, (doc_id, dist) in enumerate(
                zip(sparse_results["ids"][0], sparse_results["distances"][0])
            ):
                similarity = 1 - dist
                scores[doc_id] = scores.get(doc_id, 0) + sparse_weight * (1 / (k + rank + 1)) * similarity

        # Sort by fused score
        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)[:limit]

        # Build result
        all_ids = set(dense_results.get("ids", [[]])[0] + sparse_results.get("ids", [[]])[0])
        id_to_doc = {}
        id_to_dist = {}

        for ids_list, docs_list, dists_list in [
            (dense_results.get("ids", [[]])[0], dense_results.get("documents", [[]])[0], dense_results.get("distances", [[]])[0]),
            (sparse_results.get("ids", [[]])[0], sparse_results.get("documents", [[]])[0], sparse_results.get("distances", [[]])[0]),
        ]:
            for i, (doc_id, doc, dist) in enumerate(zip(ids_list, docs_list, dists_list)):
                id_to_doc[doc_id] = doc
                id_to_dist[doc_id] = dist

        return {
            "ids": sorted_ids,
            "documents": [id_to_doc.get(uid, "") for uid in sorted_ids],
            "distances": [1 - scores[uid] for uid in sorted_ids],  # Convert back to distance
        }

    def count(self) -> int:
        """Get collection count"""
        return self.collection.count()

    def peek(self, limit: int = 10) -> dict:
        """Peek at first N documents"""
        return self.collection.peek(limit=limit)


class ChromaVectorStore:
    """
    High-level ChromaDB vector store wrapper.

    Provides async-friendly interface for vector operations.
    """

    def __init__(
        self,
        collection_name: str,
        embedding_provider: EmbeddingProvider,
        persist_directory: str = "./data/chroma",
    ):
        self.collection_name = collection_name
        self.embedding_provider = embedding_provider
        self.persist_directory = persist_directory
        self._collection: ChromaCollection | None = None

    @property
    def collection(self) -> ChromaCollection:
        if self._collection is None:
            self._collection = ChromaCollection(
                collection_name=self.collection_name,
                embedding_function=self._get_embeddings,
                persist_directory=self.persist_directory,
            )
        return self._collection

    def _get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """
        Synchronous wrapper for embedding provider.

        Handles both async and sync contexts by detecting if we're already
        in an async context. When in async context, runs in executor to avoid blocking.
        """
        import asyncio
        import concurrent.futures

        try:
            running_loop = asyncio.get_running_loop()
            # We're in an async context - run sync embed in thread pool
            def _sync_embed():
                # Create a new event loop for this thread
                return asyncio.run(self.embedding_provider.aembed(texts))

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(_sync_embed)
                return future.result()
        except RuntimeError:
            # No running loop, safe to use asyncio.run
            return asyncio.run(self.embedding_provider.aembed(texts))

    def add_texts(
        self,
        texts: list[str],
        metadatas: list[dict] | None = None,
        ids: list[str] | None = None,
    ) -> list[str]:
        """
        Add texts with embeddings.

        Args:
            texts: Document texts
            metadatas: Optional metadata per document
            ids: Optional document IDs

        Returns:
            Document IDs
        """
        embeddings = self._get_embeddings(texts)
        return self.collection.add(
            texts=texts,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids,
        )

    def delete(self, ids: list[str]) -> None:
        """Delete documents by IDs"""
        self.collection.delete(ids=ids)

    def similarity_search(
        self,
        query: str,
        k: int = 5,
        filter_metadata: dict | None = None,
    ) -> list[tuple[str, str, float]]:
        """
        Similarity search (dense).

        Args:
            query: Query text
            k: Number of results
            filter_metadata: Metadata filter

        Returns:
            List of (id, text, score) tuples
        """
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
            )
        )

    def hybrid_search(
        self,
        query: str,
        k: int = 5,
        vector_weight: float = 0.7,
        filter_metadata: dict | None = None,
    ) -> list[tuple[str, str, float]]:
        """
        Hybrid search (dense + sparse/BM25).

        Args:
            query: Query text
            k: Number of results
            vector_weight: Weight for dense results
            filter_metadata: Metadata filter

        Returns:
            List of (id, text, score) tuples
        """
        query_embedding = self._get_embeddings([query])[0]
        ids, docs, distances = self.collection.query_hybrid(
            query_embedding=query_embedding,
            query_text=query,
            n_results=k,
            vector_weight=vector_weight,
            where_filter=filter_metadata,
        )

        return list(zip(ids, docs, [1 - d for d in distances]))

    def delete_by_kb_id(self, kb_id: str) -> int:
        """
        Delete all documents for a knowledge base.

        Args:
            kb_id: Knowledge base ID

        Returns:
            Number of documents deleted
        """
        return self.collection.delete_where({"kb_id": kb_id})

    def delete_by_file_id(self, file_id: str) -> int:
        """
        Delete all documents for a specific file.

        Args:
            file_id: File ID

        Returns:
            Number of documents deleted
        """
        return self.collection.delete_where({"file_id": file_id})

    def delete_collection(self) -> None:
        """Delete the entire collection"""
        self.collection.delete_collection()

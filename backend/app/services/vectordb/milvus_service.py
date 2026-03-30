"""
Milvus Vector Store Integration.

Provides Milvus-backed vector storage with hybrid search support.
Implements VectorDBProvider for the milvus engine.

Note: Requires `pip install pymilvus` to use this provider.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.services.vectordb.base import VectorDBProvider, VectorStore

if TYPE_CHECKING:
    from app.services.providers.base import EmbeddingProvider


class MilvusCollection:
    """
    Milvus collection wrapper implementing VectorStore protocol.
    """

    def __init__(
        self,
        collection_name: str,
        embedding_provider: EmbeddingProvider,
        connect_args: dict[str, Any],
    ):
        self.collection_name = collection_name
        self.embedding_provider = embedding_provider
        self.connect_args = connect_args
        self._client: Any = None
        self._collection: Any = None

    def _get_client(self) -> Any:
        """Lazy init Milvus client."""
        if self._client is None:
            try:
                from pymilvus import connections

                alias = f"milvus_{self.collection_name}"
                connections.connect(
                    alias=alias,
                    host=self.connect_args.get("host", "localhost"),
                    port=self.connect_args.get("port", 19530),
                    user=self.connect_args.get("user", ""),
                    password=self.connect_args.get("password", ""),
                )
                self._client = alias
            except ImportError:
                raise RuntimeError(
                    "Milvus client not installed. Run: pip install pymilvus"
                ) from None
        return self._client

    def _get_collection(self) -> Any:
        if self._collection is None:
            from pymilvus import Collection, CollectionSchema, DataType, FieldSchema

            client = self._get_client()
            # Try to get existing collection or create new one
            try:
                self._collection = Collection(self.collection_name, using=client)
                self._collection.load()
            except Exception:
                # Create collection with schema
                fields = [
                    FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=64),
                    FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
                    FieldSchema(
                        name="embedding", dtype=DataType.FLOAT_VECTOR, dim=1536
                    ),
                    FieldSchema(name="file_id", dtype=DataType.VARCHAR, max_length=64),
                    FieldSchema(name="kb_id", dtype=DataType.VARCHAR, max_length=64),
                ]
                schema = CollectionSchema(
                    fields=fields, description=self.collection_name
                )
                self._collection = Collection(
                    name=self.collection_name, schema=schema, using=client
                )
                # Create index
                index_params = {
                    "index_type": "IVF_FLAT",
                    "metric_type": "IP",
                    "params": {"nlist": 128},
                }
                self._collection.create_index(
                    field_name="embedding", index_params=index_params
                )
                self._collection.load()
        return self._collection

    @property
    def collection(self) -> Any:
        """Expose underlying Milvus collection for provider-specific access."""
        return self._get_collection()

    def add_texts(
        self,
        texts: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict] | None = None,
        ids: list[str] | None = None,
    ) -> list[str]:
        """Add documents to the collection."""
        import uuid

        collection = self._get_collection()
        if ids is None:
            ids = [str(uuid.uuid4()) for _ in texts]

        entities = [
            ids,
            texts,
            embeddings,
            [
                m.get("file_id", "") if m else ""
                for m in (metadatas or [{}] * len(texts))
            ],
            [m.get("kb_id", "") if m else "" for m in (metadatas or [{}] * len(texts))],
        ]
        collection.insert(entities)
        collection.flush()
        return ids

    def delete(self, ids: list[str]) -> None:
        """Delete documents by IDs"""
        collection = self._get_collection()
        expr = f"id in {ids}"
        collection.delete(expr)

    def delete_by_file_id(self, file_id: str) -> int:
        """Delete all documents for a specific file."""
        collection = self._get_collection()
        expr = f'file_id == "{file_id}"'
        collection.delete(expr)
        return 0  # Milvus doesn't return count

    def delete_collection(self) -> None:
        """Delete the entire collection"""
        collection = self._get_collection()
        collection.drop()

    def count(self) -> int:
        """Get collection count"""
        collection = self._get_collection()
        return collection.num_entities

    def peek(self, limit: int = 10) -> dict:
        """Peek at first N documents."""
        collection = self._get_collection()
        results = collection.query(expr="", output_fields=["*"], limit=limit)
        return {
            "ids": [r["id"] for r in results],
            "documents": [r["text"] for r in results],
        }

    def similarity_search(
        self,
        query: str,
        k: int = 5,
        filter_metadata: dict | None = None,
    ) -> list[tuple[str, str, float]]:
        """Dense vector similarity search."""
        import asyncio

        _ = filter_metadata  # Milvus doesn't support metadata filtering yet
        collection = self._get_collection()
        query_embedding = asyncio.run(self.embedding_provider.aembed([query]))[0]

        search_params = {"metric_type": "IP", "params": {"nprobe": 10}}
        results = collection.search(
            data=[query_embedding],
            anns_field="embedding",
            param=search_params,
            limit=k,
            output_fields=["id", "text"],
        )

        return [(r.entity.get("id"), r.entity.get("text"), r.score) for r in results[0]]

    def hybrid_search(
        self,
        query: str,
        k: int = 5,
        vector_weight: float = 0.7,
        filter_metadata: dict | None = None,
    ) -> list[tuple[str, str, float]]:
        """Hybrid search (same as dense for Milvus without BM25)."""
        _ = vector_weight  # Milvus doesn't support hybrid search yet
        return self.similarity_search(query, k, filter_metadata)


class MilvusProvider(VectorDBProvider):
    """
    Milvus vector database provider.

    User isolation: achieved via Milvus server-side namespace/partition.
    """

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        host: str = "localhost",
        port: int = 19530,
        user: str = "",
        password: str = "",
    ):
        super().__init__(embedding_provider=embedding_provider)
        self.host = host
        self.port = port
        self.user = user
        self.password = password

    def get_vector_store(
        self,
        collection_name: str,
        user_id: int,
    ) -> VectorStore:
        """Get a Milvus collection for the given collection name and user."""
        return MilvusCollection(
            collection_name=f"{user_id}_{collection_name}",
            embedding_provider=self.embedding_provider,
            connect_args={
                "host": self.host,
                "port": self.port,
                "user": self.user,
                "password": self.password,
            },
        )

    @property
    def engine_name(self) -> str:
        return "milvus"

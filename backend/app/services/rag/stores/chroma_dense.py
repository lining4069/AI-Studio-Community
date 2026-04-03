"""ChromaDB 稠密向量存储实现"""

from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings
from chromadb.errors import NotFoundError

from app.services.providers.base import EmbeddingProvider
from app.services.rag.stores.base import DenseStore, DocumentUnit


class ChromaDenseStore(DenseStore):
    """ChromaDB 稠密向量存储"""

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        persist_directory: str | Path,
        collection_name: str,
        user_id: int,
    ) -> None:
        self.embedding_provider = embedding_provider
        self.persist_directory = Path(persist_directory)
        self.collection_name = collection_name
        self.user_id = user_id
        self._client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"user_id": str(user_id)},
        )

    def add_documents(
        self, docs: list[DocumentUnit], embeddings: list[list[float]]
    ) -> None:
        """添加文档到 ChromaDB"""
        if not docs:
            return

        ids = [doc.document_id for doc in docs]
        texts = [doc.content for doc in docs]
        metadatas = [
            {
                "kb_id": doc.kb_id,
                "file_id": doc.file_id,
                **doc.metadata,
            }
            for doc in docs
        ]

        self._collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )

    def retrieve(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[tuple[DocumentUnit, float]]:
        """检索匹配的文档"""
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=metadata_filter,
        )

        # Handle empty results
        if not results["ids"] or not results["ids"][0]:
            return []

        doc_units = []
        for i, (doc_id, text, metadata, distance) in enumerate(
            zip(
                results["ids"][0],
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            )
        ):
            # ChromaDB 返回的是距离，转换为相似度分数
            score = 1.0 - distance if distance is not None else 0.0

            doc_unit = DocumentUnit(
                document_id=doc_id,
                kb_id=metadata.get("kb_id", ""),
                file_id=metadata.get("file_id", ""),
                content=text or "",
                metadata=metadata,
            )
            doc_units.append((doc_unit, score))

        return doc_units

    def delete_by_document_ids(self, document_ids: list[str]) -> int:
        """根据 document_id 删除文档"""
        if not document_ids:
            return 0
        self._collection.delete(ids=document_ids)
        return len(document_ids)

    def delete_by_file_id(self, file_id: str) -> int:
        """根据 file_id 删除文档"""
        try:
            results = self._collection.get(where={"file_id": file_id})
            if not results["ids"]:
                return 0
            ids = results["ids"]
            self._collection.delete(ids=ids)
            return len(ids)
        except NotFoundError:
            return 0
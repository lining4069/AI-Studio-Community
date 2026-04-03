import asyncio
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings
from chromadb.errors import NotFoundError

from app.services.providers.base import EmbeddingProvider
from app.services.rag.stores.base import DenseStore, DocumentUnit

MAX_BATCH_SIZE = 64  # 插入批次安全阈值


class ChromaDenseStore(DenseStore):
    """ChromaDB 稠密向量存储（优化版）"""

    EMBEDDING_BATCH_SIZE = 100

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

        self._client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"user_id": str(user_id)},
        )

    # -------------------------
    # 工具：分批
    # -------------------------
    @staticmethod
    def _chunk(items: list, size: int) -> list[list]:
        return [items[i : i + size] for i in range(0, len(items), size)]

    # -------------------------
    # 插入文档
    # -------------------------
    async def add_documents(self, docs: list[DocumentUnit]) -> None:
        """
        添加文档到 ChromaDB
        批量生成 embedding + 异步写入
        返回实际插入数量
        """
        if not docs:
            return None

        provider_batch = getattr(self.embedding_provider, "batch_size", 10)
        batch_size = min(provider_batch, self.EMBEDDING_BATCH_SIZE)

        for chunk in self._chunk(docs, batch_size):
            ids = [doc.document_id for doc in chunk]
            texts = [doc.content for doc in chunk]
            metadatas = [
                {"kb_id": doc.kb_id, "file_id": doc.file_id, **doc.metadata}
                for doc in chunk
            ]

            try:
                embeddings = await self.embedding_provider.aembed(texts)

                def _sync_add():
                    self._collection.add(
                        ids=ids,
                        embeddings=embeddings,
                        documents=texts,
                        metadatas=metadatas,
                    )

                await asyncio.to_thread(_sync_add)

            except Exception as e:
                # 记录异常，继续处理下一批
                print(f"ChromaDenseStore batch insert failed: {e}")

    # -------------------------
    # 检索
    # -------------------------
    async def retrieve(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[tuple[DocumentUnit, float]]:
        """
        检索匹配的文档
        返回 (DocumentUnit, score)
        """

        def _sync_query():
            return self._collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=metadata_filter,
            )

        results = await asyncio.to_thread(_sync_query)

        if not results["ids"] or not results["ids"][0]:
            return []

        doc_units = []
        for doc_id, text, metadata, distance in zip(
            results["ids"][0],
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            score = 1.0 - (distance if distance is not None else 1.0)
            doc_units.append(
                (
                    DocumentUnit(
                        document_id=doc_id,
                        kb_id=metadata.get("kb_id", ""),
                        file_id=metadata.get("file_id", ""),
                        content=text or "",
                        metadata=metadata,
                    ),
                    float(score),
                )
            )

        return doc_units

    # -------------------------
    # 删除
    # -------------------------
    async def delete_by_document_ids(self, document_ids: list[str]) -> int:
        if not document_ids:
            return 0

        try:

            def _sync_delete():
                self._collection.delete(ids=document_ids)

            await asyncio.to_thread(_sync_delete)
            return len(document_ids)
        except NotFoundError:
            return 0

    async def delete_by_file_id(self, file_id: str) -> int:
        try:

            def _sync_get_and_delete():
                results = self._collection.get(where={"file_id": file_id})
                if not results["ids"]:
                    return 0
                self._collection.delete(ids=results["ids"])
                return len(results["ids"])

            return await asyncio.to_thread(_sync_get_and_delete)
        except NotFoundError:
            return 0

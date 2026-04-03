import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.dependencies.infras.database import AsyncSessionFactory
from app.services.providers.base import EmbeddingProvider
from app.services.rag.stores.base import DenseStore, DocumentUnit


class PGDenseStore(DenseStore):
    """PostgreSQL + pgvector 稠密向量存储（最终生产版）"""

    # API embedding 单次请求上限（安全阈值，防止 token 超限）
    EMBEDDING_BATCH_SIZE = 100

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        table_name: str = "pg_chunks",
        sessionmaker: async_sessionmaker[AsyncSession] = AsyncSessionFactory,
    ) -> None:
        self.embedding_provider = embedding_provider
        self.table_name = table_name
        self.sessionmaker = sessionmaker

    # ========================
    # 工具：分批
    # ========================
    @staticmethod
    def _chunk(items: list, size: int) -> list[list]:
        """均分列表，不足时按实际长度切分"""
        return [items[i : i + size] for i in range(0, len(items), size)]

    # ========================
    # 插入（批量 + 分块 + 事务）
    # ========================
    async def add_documents(self, docs: list[DocumentUnit]) -> None:
        """
        添加文档到稠密存储

        分块嵌入：按 batch_size 分批调用 embedding API，
        避免单次请求 token 超限。每批完成后立即写入 DB。

        Args:
            docs: 文档列表
        """
        if not docs:
            return

        # 使用 embedding_provider 的 batch_size，兜底为 EMBEDDING_BATCH_SIZE
        provider_batch = getattr(self.embedding_provider, "batch_size", None) or 10
        batch_size = min(provider_batch, self.EMBEDDING_BATCH_SIZE)

        insert_sql = text(f"""
            INSERT INTO {self.table_name}
            (id, document_id, kb_id, file_id, content, embedding, metadata)
            VALUES
            (:id, :document_id, :kb_id, :file_id, :content, :embedding, :metadata)
        """)

        async with self.sessionmaker() as db:
            async with db.begin():
                for chunk in self._chunk(docs, batch_size):
                    texts = [doc.content for doc in chunk]
                    embeddings = await self.embedding_provider.aembed(texts)

                    payload = [
                        {
                            "id": doc.document_id,
                            "document_id": doc.document_id,
                            "kb_id": doc.kb_id,
                            "file_id": doc.file_id,
                            "content": doc.content,
                            "embedding": emb,
                            "metadata": doc.metadata,
                        }
                        for doc, emb in zip(chunk, embeddings)
                    ]
                    await db.execute(insert_sql, payload)

    # ========================
    # 检索（向量相似度）
    # ========================
    async def retrieve(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[tuple[DocumentUnit, float]]:

        base_sql = f"""
        SELECT id, document_id, kb_id, file_id, content, metadata,
               1 - (embedding <=> :embedding) AS score
        FROM {self.table_name}
        """

        params: dict[str, Any] = {
            "embedding": query_embedding,
            "top_k": top_k,
        }

        # ========================
        # metadata 过滤（安全 + 可扩展）
        # ========================
        if metadata_filter:
            conditions = []
            for i, (key, value) in enumerate(metadata_filter.items()):
                safe_key = re.sub(r"[^a-zA-Z0-9_]", "", key)
                if not safe_key:
                    continue

                param_key = f"meta_{i}"
                conditions.append(f"metadata ->> '{safe_key}' = :{param_key}")
                params[param_key] = str(value)

            if conditions:
                base_sql += " WHERE " + " AND ".join(conditions)

        # ⚠️ 必须用距离排序（才能走 ivfflat）
        base_sql += " ORDER BY embedding <=> :embedding LIMIT :top_k"

        async with self.sessionmaker() as db:
            result = await db.execute(text(base_sql), params)
            rows = result.fetchall()

        return [
            (
                DocumentUnit(
                    document_id=row.document_id,
                    kb_id=row.kb_id,
                    file_id=row.file_id,
                    content=row.content,
                    metadata=row.metadata or {},
                ),
                float(row.score),
            )
            for row in rows
        ]

    # ========================
    # 删除（批量）
    # ========================
    async def delete_by_document_ids(self, document_ids: list[str]) -> int:
        if not document_ids:
            return 0

        sql = text(f"""
            DELETE FROM {self.table_name}
            WHERE document_id = ANY(:document_ids)
        """)

        async with self.sessionmaker() as db:
            async with db.begin():
                result = await db.execute(sql, {"document_ids": document_ids})
                return result.rowcount or 0

    async def delete_by_file_id(self, file_id: str) -> int:
        sql = text(f"""
            DELETE FROM {self.table_name}
            WHERE file_id = :file_id
        """)

        async with self.sessionmaker() as db:
            async with db.begin():
                result = await db.execute(sql, {"file_id": file_id})
                return result.rowcount or 0

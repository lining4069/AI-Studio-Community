import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.rag.stores.base import DenseStore, DocumentUnit


class PGDenseStore(DenseStore):
    """PostgreSQL + pgvector 稠密向量存储（生产级实现）"""

    def __init__(
        self,
        db_session: AsyncSession,
        table_name: str = "pg_chunks",
    ) -> None:
        self.db = db_session
        self.table_name = table_name

    # ========================
    # 插入（批量 + async）
    # ========================
    async def add_documents(
        self,
        docs: list[DocumentUnit],
        embeddings: list[list[float]],
    ) -> None:
        if not docs:
            return

        insert_sql = text(f"""
            INSERT INTO {self.table_name}
            (id, document_id, kb_id, file_id, chunk_index, content, embedding, metadata)
            VALUES
            (:id, :document_id, :kb_id, :file_id, :chunk_index, :content, :embedding, :metadata)
        """)

        payload = []
        for doc, embedding in zip(docs, embeddings):
            payload.append(
                {
                    "id": doc.document_id,
                    "document_id": doc.document_id,
                    "kb_id": doc.kb_id,
                    "file_id": doc.file_id,
                    "chunk_index": doc.chunk_index,
                    "content": doc.content,
                    "embedding": embedding,
                    "metadata": doc.metadata,
                }
            )

        await self.db.execute(insert_sql, payload)
        await self.db.commit()

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
        SELECT id, document_id, kb_id, file_id, chunk_index, content, metadata,
               1 - (embedding <=> :embedding) AS score
        FROM {self.table_name}
        """

        params: dict[str, Any] = {
            "embedding": query_embedding,
            "top_k": top_k,
        }

        # ========================
        # metadata filter（修复安全问题）
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

        # ⚠️ pgvector 核心排序（必须）
        base_sql += " ORDER BY embedding <=> :embedding LIMIT :top_k"

        result = await self.db.execute(text(base_sql), params)
        rows = result.fetchall()

        return [
            (
                DocumentUnit(
                    document_id=row.document_id,
                    kb_id=row.kb_id,
                    file_id=row.file_id,
                    chunk_index=row.chunk_index,
                    content=row.content,
                    metadata=row.metadata or {},
                ),
                float(row.score),
            )
            for row in rows
        ]

    # ========================
    # 删除
    # ========================
    async def delete_by_document_ids(self, document_ids: list[str]) -> int:
        if not document_ids:
            return 0

        sql = text(f"""
            DELETE FROM {self.table_name}
            WHERE document_id = ANY(:document_ids)
        """)

        result = await self.db.execute(sql, {"document_ids": document_ids})
        await self.db.commit()
        return result.rowcount or 0

    async def delete_by_file_id(self, file_id: str) -> int:
        sql = text(f"""
            DELETE FROM {self.table_name}
            WHERE file_id = :file_id
        """)

        result = await self.db.execute(sql, {"file_id": file_id})
        await self.db.commit()
        return result.rowcount or 0

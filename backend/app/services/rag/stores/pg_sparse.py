import re
from typing import Any

import jieba
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.rag.stores.base import DocumentUnit, SparseStore


class PGSparseStore(SparseStore):
    """PostgreSQL + jieba 稀疏存储（生产级实现）"""

    STOPWORDS = {"的", "了", "是", "在"}  # 可扩展

    def __init__(
        self,
        db_session: AsyncSession,
        table_name: str = "pg_sparse_chunks",
    ) -> None:
        self.db = db_session
        self.table_name = table_name

    # ========================
    # Tokenize（核心）
    # ========================
    def _tokenize(self, text: str) -> str:
        tokens = [
            w.strip()
            for w in jieba.lcut_for_search(text)
            if w.strip() and w not in self.STOPWORDS
        ]
        return " ".join(tokens)

    # ========================
    # 插入（批量 + 直接生成 tsv）
    # ========================
    async def add_documents(self, docs: list[DocumentUnit]) -> None:
        if not docs:
            return

        insert_sql = text(f"""
            INSERT INTO {self.table_name}
            (id, document_id, kb_id, file_id, content, tokens, metadata, tsv)
            VALUES
            (:id, :document_id, :kb_id, :file_id, :content, :tokens, :metadata, to_tsvector('simple', :tokens))
        """)

        payload = []
        for doc in docs:
            tokens = self._tokenize(doc.content)
            payload.append(
                {
                    "id": doc.document_id,
                    "document_id": doc.document_id,
                    "kb_id": doc.kb_id,
                    "file_id": doc.file_id,
                    "content": doc.content,
                    "tokens": tokens,
                    "metadata": doc.metadata,
                }
            )

        await self.db.execute(insert_sql, payload)
        await self.db.commit()

    # ========================
    # 检索（核心优化）
    # ========================
    async def retrieve(
        self,
        query: str,
        top_k: int = 10,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[tuple[DocumentUnit, float]]:

        # ✅ query 分词（必须）
        query_tokens = self._tokenize(query)

        base_sql = f"""
        WITH q AS (
            SELECT plainto_tsquery('simple', :query) AS query
        )
        SELECT id, document_id, kb_id, file_id, content, metadata,
               ts_rank(tsv, q.query, 32) AS score
        FROM {self.table_name}, q
        WHERE tsv @@ q.query
        """

        params: dict[str, Any] = {
            "query": query_tokens,
            "top_k": top_k,
        }

        # ========================
        # metadata filter（安全写法）
        # ========================
        if metadata_filter:
            for i, (key, value) in enumerate(metadata_filter.items()):
                safe_key = re.sub(r"[^a-zA-Z0-9_]", "", key)
                if not safe_key:
                    continue
                param_key = f"meta_{i}"
                base_sql += f" AND metadata ->> '{safe_key}' = :{param_key}"
                params[param_key] = str(value)

        base_sql += " ORDER BY score DESC LIMIT :top_k"

        result = await self.db.execute(text(base_sql), params)
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

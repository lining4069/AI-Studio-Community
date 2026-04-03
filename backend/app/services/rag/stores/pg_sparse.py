import json
import re
from collections.abc import Generator
from typing import Any

import jieba
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.dependencies.infras.database import AsyncSessionFactory
from app.services.rag.stores.base import DocumentUnit, SparseStore

MAX_BATCH_SIZE = 64  # 批量控制


class PGSparseStore(SparseStore):
    """PostgreSQL + jieba 稀疏存储（BM25，生产级最终版，支持批次处理）"""

    STOPWORDS = {"的", "了", "是", "在"}

    def __init__(
        self,
        table_name: str = "pg_sparse_chunks",
    ) -> None:
        self.table_name = table_name
        self.sessionmaker: async_sessionmaker[AsyncSession] = AsyncSessionFactory

    # ========================
    # 分词（写入 & 查询统一）
    # ========================
    def _tokenize(self, text: str) -> str:
        tokens = [
            w.strip()
            for w in jieba.lcut_for_search(text)
            if w.strip() and w not in self.STOPWORDS
        ]
        return " ".join(tokens)

    # ========================
    # 工具：生成器分批
    # ========================
    @staticmethod
    def _chunk_generator(
        items: list[DocumentUnit], size: int
    ) -> Generator[list[DocumentUnit], None, None]:
        """生成器批量分块"""
        for i in range(0, len(items), size):
            yield items[i : i + size]

    # ========================
    # 插入（批量 + 事务）
    # ========================
    async def add_documents(self, docs: list[DocumentUnit]) -> None:
        if not docs:
            return

        insert_sql = text(f"""
            INSERT INTO {self.table_name}
            (id, document_id, kb_id, file_id, content, tokens, metadata)
            VALUES
            (:id, :document_id, :kb_id, :file_id, :content, :tokens, :metadata)
        """)

        async with self.sessionmaker() as db:
            async with db.begin():
                for chunk in self._chunk_generator(docs, MAX_BATCH_SIZE):
                    payload = []
                    for doc in chunk:
                        tokens = self._tokenize(doc.content)
                        payload.append(
                            {
                                "id": doc.document_id,
                                "document_id": doc.document_id,
                                "kb_id": doc.kb_id,
                                "file_id": doc.file_id,
                                "content": doc.content,
                                "tokens": tokens,
                                "metadata": json.dumps(doc.metadata)
                                if doc.metadata
                                else {},
                            }
                        )
                    await db.execute(insert_sql, payload)

    # ========================
    # 检索（BM25 + metadata）
    # ========================
    async def retrieve(
        self,
        query: str,
        top_k: int = 10,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[tuple[DocumentUnit, float]]:

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

        params: dict[str, Any] = {"query": query_tokens, "top_k": top_k}

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
                base_sql += " AND " + " AND ".join(conditions)

        base_sql += " ORDER BY score DESC LIMIT :top_k"

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
    # 删除接口
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

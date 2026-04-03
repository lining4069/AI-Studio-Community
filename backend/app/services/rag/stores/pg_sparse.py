import re
from collections.abc import Generator
from typing import Any

from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.dependencies.infras.database import AsyncSessionFactory
from app.services.rag.stores.base import DocumentUnit, SparseStore

MAX_BATCH_SIZE = 64  # 稀疏插入批量控制


class PGSparseStore(SparseStore):
    """PostgreSQL 稀疏向量 / tsvector 存储
    生产级实现 + 支持批量插入和 metadata 查询
    类似 LangChain-Chroma 接口风格
    """

    def __init__(
        self,
        table_name: str = "pg_sparse_chunks",
        sessionmaker: async_sessionmaker[AsyncSession] = AsyncSessionFactory,
    ) -> None:
        self.table_name = table_name
        self.sessionmaker = sessionmaker

    # -------------------------
    # 工具：分块生成器
    # -------------------------
    @staticmethod
    def _chunk_generator(
        items: list[DocumentUnit], size: int
    ) -> Generator[list[DocumentUnit], None, None]:
        """生成器批量分块"""
        for i in range(0, len(items), size):
            yield items[i : i + size]

    # -------------------------
    # 插入文档
    # -------------------------
    async def add_documents(self, docs: list[DocumentUnit]) -> None:
        """
        批量插入稀疏文档

        每批写入数据库，异常安全，返回实际插入数量。
        tsv 字段自动生成。
        """
        if not docs:
            return None

        insert_sql = text(f"""
            INSERT INTO {self.table_name}
            (id, document_id, kb_id, file_id, content, tokens, metadata)
            VALUES
            (:id, :document_id, :kb_id, :file_id, :content, :tokens, :metadata)
        """)

        async with self.sessionmaker() as db:
            async with db.begin():
                for chunk in self._chunk_generator(docs, MAX_BATCH_SIZE):
                    payload = [
                        {
                            "id": doc.document_id,
                            "document_id": doc.document_id,
                            "kb_id": doc.kb_id,
                            "file_id": doc.file_id,
                            "content": doc.content,
                            "tokens": doc.content,  # tsvector 会用 tokens 生成
                            "metadata": doc.metadata,
                        }
                        for doc in chunk
                    ]

                    try:
                        await db.execute(insert_sql, payload)
                    except Exception as e:
                        logger.error(f"PGSparseStore insert batch failed: {e}")

    # -------------------------
    # 检索（tsvector + metadata）
    # -------------------------
    async def retrieve(
        self,
        query: str,
        top_k: int = 10,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[tuple[DocumentUnit, float]]:
        """
        基于全文检索 + metadata 过滤
        返回 top_k 文档及匹配分数
        """
        base_sql = f"""
        SELECT id, document_id, kb_id, file_id, content, metadata,
               ts_rank_cd(tsv, plainto_tsquery('simple', :query)) AS score
        FROM {self.table_name}
        """

        params: dict[str, Any] = {"query": query, "top_k": top_k}

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

        base_sql += " ORDER BY score DESC LIMIT :top_k"

        async with self.sessionmaker() as db:
            result = await db.execute(text(base_sql), params)
            rows = await result.fetchall()

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

    # -------------------------
    # 删除
    # -------------------------
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

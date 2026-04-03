import json
import re
from collections.abc import Generator
from typing import Any

from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.dependencies.infras.database import AsyncSessionFactory
from app.services.providers.base import EmbeddingProvider
from app.services.rag.stores.base import DenseStore, DocumentUnit

MAX_EMBEDDING_BATCH = 100  # 每批调用 embedding API 的上限


class PGDenseStore(DenseStore):
    """PostgreSQL + pgvector 稠密向量存储
    生产级实现 + 支持 EmbeddingProvider 批量生成
    类似 LangChain-Chroma 风格接口
    """

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        table_name: str = "pg_chunks",
        sessionmaker: async_sessionmaker[AsyncSession] = AsyncSessionFactory,
    ) -> None:
        self.embedding_provider = embedding_provider
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
    # 工具：list[float] → PostgreSQL vector 字面量
    # -------------------------
    @staticmethod
    def _vec_to_str(v: list[float]) -> str:
        """
        将 embedding 向量转为 PostgreSQL vector 字面量字符串

        asyncpg.executemany() 无法直接发送 Python list[float] 到 PostgreSQL vector 列，
        转为字符串后由数据库的 ::vector 强制类型转换解析。
        """
        return f"[{','.join(str(x) for x in v)}]"

    # -------------------------
    # 插入文档
    # -------------------------
    async def add_documents(self, docs: list[DocumentUnit]) -> None:
        """
        添加文档到稠密存储

        支持批量嵌入，每批写入数据库，失败记录日志，不中断其他批次。
        返回实际插入的文档数量。

        Args:
            docs: 文档列表

        Returns:
            int: 插入成功文档数
        """
        if not docs:
            return None

        batch_size = min(
            getattr(self.embedding_provider, "batch_size", 10), MAX_EMBEDDING_BATCH
        )

        async with self.sessionmaker() as db:
            async with db.begin():  # 事务保护
                for chunk in self._chunk_generator(docs, batch_size):
                    texts = [doc.content for doc in chunk]

                    try:
                        embeddings = await self.embedding_provider.aembed(texts)
                    except Exception as e:
                        logger.error(f"Embedding API failed for batch: {e}")
                        # 对应批次 embeddings 全置为 0 向量，避免中断
                        embeddings = [
                            [0.0] * self.embedding_provider.dimension for _ in chunk
                        ]

                    # 构造批量 INSERT VALUES
                    # list[float] → str('[v1,v2,...]')，用 ::vector 让 PG 解析
                    rows: list[tuple[Any, ...]] = []
                    for doc, emb in zip(chunk, embeddings):
                        rows.append(
                            (
                                doc.document_id,
                                doc.kb_id,
                                doc.file_id,
                                doc.content,
                                self._vec_to_str(emb),  # str，PG 用 ::vector 解析
                                doc.metadata,
                            )
                        )

                    cols = (
                        "id, document_id, kb_id, file_id, content, embedding, metadata"
                    )
                    single_insert_sql = text(
                        f"INSERT INTO {self.table_name} ({cols}) VALUES (:id, :document_id, :kb_id, :file_id, :content, cast(:embedding as vector), :metadata)"
                    )
                    for row in rows:
                        await db.execute(
                            single_insert_sql,
                            {
                                "id": row[0],
                                "document_id": row[0],
                                "kb_id": row[1],
                                "file_id": row[2],
                                "content": row[3],
                                "embedding": row[4],
                                "metadata": json.dumps(row[5]) if row[5] else {},
                            },
                        )

    # -------------------------
    # 检索
    # -------------------------
    async def retrieve(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[tuple[DocumentUnit, float]]:
        base_sql = f"""
        SELECT id, document_id, kb_id, file_id, content, metadata,
               1 - (embedding <=> cast(:embedding as vector)) AS score
        FROM {self.table_name}
        """

        params: dict[str, Any] = {
            "embedding": self._vec_to_str(query_embedding),
            "top_k": top_k,
        }

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

        base_sql += " ORDER BY embedding <=> cast(:embedding as vector) LIMIT :top_k"

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

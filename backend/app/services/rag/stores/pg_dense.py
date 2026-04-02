"""PostgreSQL + pgvector 稠密向量存储实现"""

import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.providers.base import EmbeddingProvider
from app.services.rag.stores.base import DenseStore, DocumentUnit


class PGDenseStore(DenseStore):
    """PostgreSQL + pgvector 稠密向量存储"""

    def __init__(
        self,
        db_session: AsyncSession,
        embedding_provider: EmbeddingProvider,
        table_name: str = "pg_chunks",
    ) -> None:
        self.db = db_session
        self.embedding_provider = embedding_provider
        self.table_name = table_name

    def _build_insert_sql(self) -> str:
        """构建插入 SQL"""
        return f"""
            INSERT INTO {self.table_name}
            (id, document_id, kb_id, file_id, chunk_index, content, embedding, metadata)
            VALUES
            (:id, :document_id, :kb_id, :file_id, :chunk_index, :content, :embedding, :metadata::jsonb)
        """

    def _build_delete_by_doc_ids_sql(self) -> str:
        """构建按 document_id 删除的 SQL"""
        return f"""
            DELETE FROM {self.table_name} WHERE document_id = ANY(:document_ids)
        """

    def _build_delete_by_file_id_sql(self) -> str:
        """构建按 file_id 删除的 SQL"""
        return f"""
            DELETE FROM {self.table_name} WHERE file_id = :file_id
        """

    def add_documents(
        self, docs: list[DocumentUnit], embeddings: list[list[float]]
    ) -> None:
        """添加文档到 PostgreSQL"""
        if not docs:
            return

        insert_sql = self._build_insert_sql()

        for doc, embedding in zip(docs, embeddings):
            self.db.execute(
                text(insert_sql),
                {
                    "id": doc.document_id,
                    "document_id": doc.document_id,
                    "kb_id": doc.kb_id,
                    "file_id": doc.file_id,
                    "chunk_index": doc.chunk_index,
                    "content": doc.content,
                    "embedding": embedding,
                    "metadata": doc.metadata,
                },
            )

    def retrieve(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[tuple[DocumentUnit, float]]:
        """检索匹配的文档"""
        retrieve_sql = f"""
            SELECT id, document_id, kb_id, file_id, chunk_index, content, metadata,
                   1 - (embedding <=> :embedding) AS score
            FROM {self.table_name}
        """

        params: dict[str, Any] = {
            "embedding": query_embedding,
            "top_k": top_k,
        }

        where_clauses = []
        if metadata_filter:
            for key, value in metadata_filter.items():
                safe_key = re.sub(r'[^a-zA-Z0-9_]', '', key)
                if not safe_key:
                    continue  # skip invalid keys
                where_clauses.append(f"metadata->>:{safe_key} = :{safe_key}")
                params[safe_key] = str(value)

        if where_clauses:
            retrieve_sql += " WHERE " + " AND ".join(where_clauses)

        retrieve_sql += f" ORDER BY embedding <=> :embedding LIMIT :top_k"

        result = self.db.execute(text(retrieve_sql), params)
        rows = result.fetchall()

        doc_units = []
        for row in rows:
            doc_unit = DocumentUnit(
                document_id=row.document_id,
                kb_id=row.kb_id,
                file_id=row.file_id,
                chunk_index=row.chunk_index,
                content=row.content,
                metadata=row.metadata or {},
            )
            doc_units.append((doc_unit, float(row.score)))

        return doc_units

    def delete_by_document_ids(self, document_ids: list[str]) -> int:
        """根据 document_id 删除文档"""
        if not document_ids:
            return 0
        delete_sql = self._build_delete_by_doc_ids_sql()
        result = self.db.execute(
            text(delete_sql), {"document_ids": document_ids}
        )
        return result.rowcount or 0

    def delete_by_file_id(self, file_id: str) -> int:
        """根据 file_id 删除文档"""
        delete_sql = self._build_delete_by_file_id_sql()
        result = self.db.execute(text(delete_sql), {"file_id": file_id})
        return result.rowcount or 0

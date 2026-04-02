"""PostgreSQL + jieba 稀疏存储实现（BM25）"""

from typing import Any

import jieba
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.rag.stores.base import DocumentUnit, SparseStore


class PGSparseStore(SparseStore):
    """PostgreSQL + jieba 稀疏存储（BM25）"""

    def __init__(
        self,
        db_session: AsyncSession,
        table_name: str = "pg_sparse_chunks",
    ) -> None:
        self.db = db_session
        self.table_name = table_name

    def _tokenize(self, text: str) -> str:
        """使用 jieba 分词，返回空格分隔的 token 字符串"""
        return " ".join(jieba.cut(text))

    def _build_insert_sql(self) -> str:
        """构建插入 SQL"""
        return f"""
            INSERT INTO {self.table_name}
            (id, document_id, kb_id, file_id, chunk_index, content, tokens, metadata)
            VALUES
            (:id, :document_id, :kb_id, :file_id, :chunk_index, :content, :tokens, :metadata::jsonb)
        """

    def _build_retrieve_sql(self) -> str:
        """构建检索 SQL（BM25 使用 ts_rank）"""
        return f"""
            SELECT id, document_id, kb_id, file_id, chunk_index, content, metadata,
                   ts_rank(to_tsvector('simple', tokens), plainto_tsquery('simple', :query)) AS score
            FROM {self.table_name}
            WHERE to_tsvector('simple', tokens) @@ plainto_tsquery('simple', :query)
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

    def add_documents(self, docs: list[DocumentUnit]) -> None:
        """添加文档到稀疏存储（写入时完成 jieba 分词）"""
        if not docs:
            return

        insert_sql = self._build_insert_sql()

        for doc in docs:
            tokens = self._tokenize(doc.content)
            self.db.execute(
                text(insert_sql),
                {
                    "id": doc.document_id,
                    "document_id": doc.document_id,
                    "kb_id": doc.kb_id,
                    "file_id": doc.file_id,
                    "chunk_index": doc.chunk_index,
                    "content": doc.content,
                    "tokens": tokens,
                    "metadata": doc.metadata,
                },
            )

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[tuple[DocumentUnit, float]]:
        """检索匹配的文档"""
        # 对查询进行分词
        query_tokens = self._tokenize(query)

        retrieve_sql = f"""
            SELECT id, document_id, kb_id, file_id, chunk_index, content, metadata,
                   ts_rank(to_tsvector('simple', tokens), plainto_tsquery('simple', :query)) AS score
            FROM {self.table_name}
            WHERE to_tsvector('simple', tokens) @@ plainto_tsquery('simple', :query)
        """

        params: dict[str, Any] = {
            "query": query_tokens,
            "top_k": top_k,
        }

        where_clauses = []
        if metadata_filter:
            import re
            for key, value in metadata_filter.items():
                safe_key = re.sub(r'[^a-zA-Z0-9_]', '', key)
                if not safe_key:
                    continue
                where_clauses.append(f"metadata->>:{safe_key} = :{safe_key}")
                params[safe_key] = str(value)

        if where_clauses:
            retrieve_sql += " AND " + " AND ".join(where_clauses)

        retrieve_sql += f" ORDER BY score DESC LIMIT :top_k"

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

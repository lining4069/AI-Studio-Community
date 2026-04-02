"""RAG Index Service — 文档索引管道"""

import uuid
from pathlib import Path
from typing import Any

from loguru import logger

from app.services.providers.base import EmbeddingProvider
from app.services.rag.document_loader import DocumentLoader
from app.services.rag.stores.base import DenseStore, DocumentUnit, SparseStore
from app.services.rag.text_splitter import TextSplitter


class RAGIndexService:
    """
    RAG 索引服务

    处理文档索引流程：
    file → DocumentLoader → chunks → embeddings → vector store
                                              → sparse store

    依赖：
    - dense_store: DenseStore
    - sparse_store: SparseStore
    - embedding_provider: EmbeddingProvider
    - document_loader: DocumentLoader
    - text_splitter: TextSplitter
    """

    def __init__(
        self,
        dense_store: DenseStore,
        sparse_store: SparseStore,
        embedding_provider: EmbeddingProvider,
        document_loader: DocumentLoader | None = None,
        text_splitter: TextSplitter | None = None,
    ) -> None:
        self.dense_store = dense_store
        self.sparse_store = sparse_store
        self.embedding_provider = embedding_provider
        self.document_loader = document_loader or DocumentLoader()
        self.text_splitter = text_splitter or TextSplitter()

    async def index_document(
        self,
        file_path: str | Path,
        kb_id: str,
        file_id: str,
        user_id: int,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[int, list[str]]:
        """
        索引文档

        Args:
            file_path: 文件路径
            kb_id: 知识库 ID
            file_id: 文件 ID
            user_id: 用户 ID
            metadata: 额外元数据

        Returns:
            (chunk_count, document_ids)
        """
        # 1. 加载文档
        docs = self.document_loader.load_with_metadata(
            file_path,
            metadata={"kb_id": kb_id, "file_id": file_id, "user_id": user_id},
        )

        # 2. 分块
        chunks = self.text_splitter.split_documents(docs)

        if not chunks:
            return 0, []

        # 3. 生成 document_ids（外部传入 UUID）
        document_ids = [str(uuid.uuid4()) for _ in chunks]

        # 4. 构建 DocumentUnits
        doc_units = []
        for i, chunk in enumerate(chunks):
            doc_unit = DocumentUnit(
                document_id=document_ids[i],
                kb_id=kb_id,
                file_id=file_id,
                chunk_index=i,
                content=chunk.page_content,
                metadata=chunk.metadata,
            )
            doc_units.append(doc_unit)

        # 5. 计算 embeddings
        texts = [u.content for u in doc_units]
        embeddings = await self.embedding_provider.aembed(texts)

        # 6. 写入 DenseStore
        self.dense_store.add_documents(doc_units, embeddings)

        # 7. 写入 SparseStore（jieba 分词在内部处理）
        self.sparse_store.add_documents(doc_units)

        return len(doc_units), document_ids

    def delete_document(self, file_id: str) -> int:
        """
        删除文档

        Args:
            file_id: 文件 ID

        Returns:
            删除的块数量
        """
        deleted_dense = self.dense_store.delete_by_file_id(file_id)
        deleted_sparse = self.sparse_store.delete_by_file_id(file_id)
        if deleted_dense != deleted_sparse:
            logger.warning(f"Delete mismatch: dense={deleted_dense}, sparse={deleted_sparse}")
        return max(deleted_dense, deleted_sparse)

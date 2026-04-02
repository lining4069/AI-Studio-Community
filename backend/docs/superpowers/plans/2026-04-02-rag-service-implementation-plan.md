# RAG Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 RAG 核心服务和索引/检索管道，支持 ChromaDB 和 PostgreSQL (pgvector + jieba) 两种后端

**Architecture:** 通过抽象基类 `DenseStore` 和 `SparseStore` 定义接口，`ChromaDenseStore` / `PGDenseStore` 实现稠密向量存储，`PGSparseStore` 实现稀疏 BM25 存储。`RAGIndexService` 负责文档索引，`RAGRetrievalService` 负责混合检索和 RRF 融合。

**Tech Stack:** Python 3.11+, SQLAlchemy 2.0 (async), asyncpg, pgvector, chromadb, jieba, langchain-community, langchain-text-splitters

---

## 文件结构

```
app/services/rag/
├── __init__.py                       # 更新：导出新类
├── service_factory.py                 # 更新：添加 create_rag_index_service, create_rag_retrieval_service
├── document_loader.py                 # 新：DocumentLoader
├── text_splitter.py                  # 新：TextSplitter
├── index_service.py                  # 新：RAGIndexService
├── retrieval_service.py               # 新：RAGRetrievalService
└── stores/
    ├── __init__.py                   # 新：stores 包导出
    ├── base.py                      # 新：DenseStore (ABC), SparseStore (ABC), DocumentUnit
    ├── chroma_dense.py               # 新：ChromaDenseStore
    ├── pg_dense.py                   # 新：PGDenseStore
    └── pg_sparse.py                  # 新：PGSparseStore
```

---

## Task 1: 创建 stores/base.py — 核心抽象基类和 DocumentUnit

**Files:**
- Create: `app/services/rag/stores/base.py`

- [ ] **Step 1: 创建目录结构**

```bash
mkdir -p app/services/rag/stores
touch app/services/rag/stores/__init__.py
```

- [ ] **Step 2: 编写 DocumentUnit 和抽象基类**

```python
"""RAG Store 抽象基类和核心数据结构"""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class DocumentUnit(BaseModel):
    """RAG 模块/服务中循环流通的数据结构"""
    document_id: str          # 外部生成的 UUID
    kb_id: str
    file_id: str
    chunk_index: int
    content: str              # 原始文本
    metadata: dict = {}       # 额外元数据


class DenseStore(ABC):
    """稠密向量存储抽象基类"""

    @abstractmethod
    def add_documents(
        self, docs: list[DocumentUnit], embeddings: list[list[float]]
    ) -> None:
        """添加文档到稠密存储"""
        pass

    @abstractmethod
    def retrieve(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[tuple[DocumentUnit, float]]:
        """
        检索匹配的文档

        Returns:
            list of (DocumentUnit, score)
        """
        pass

    @abstractmethod
    def delete_by_document_ids(self, document_ids: list[str]) -> int:
        """根据 document_id 删除文档"""
        pass

    @abstractmethod
    def delete_by_file_id(self, file_id: str) -> int:
        """根据 file_id 删除文档"""
        pass


class SparseStore(ABC):
    """稀疏存储抽象基类（BM25 关键词检索）"""

    @abstractmethod
    def add_documents(self, docs: list[DocumentUnit]) -> None:
        """添加文档到稀疏存储（写入时完成 jieba 分词）"""
        pass

    @abstractmethod
    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[tuple[DocumentUnit, float]]:
        """
        检索匹配的文档

        Returns:
            list of (DocumentUnit, score)
        """
        pass

    @abstractmethod
    def delete_by_document_ids(self, document_ids: list[str]) -> int:
        """根据 document_id 删除文档"""
        pass

    @abstractmethod
    def delete_by_file_id(self, file_id: str) -> int:
        """根据 file_id 删除文档"""
        pass
```

- [ ] **Step 3: 提交**

```bash
git add app/services/rag/stores/__init__.py app/services/rag/stores/base.py
git commit -m "feat(rag): add DocumentUnit, DenseStore and SparseStore ABCs"
```

---

## Task 2: 创建 stores/chroma_dense.py — ChromaDenseStore

**Files:**
- Create: `app/services/rag/stores/chroma_dense.py`
- Modify: `app/services/rag/stores/__init__.py`

- [ ] **Step 1: 编写 ChromaDenseStore**

```python
"""ChromaDB 稠密向量存储实现"""

from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.services.providers.base import EmbeddingProvider
from app.services.rag.stores.base import DenseStore, DocumentUnit


class ChromaDenseStore(DenseStore):
    """ChromaDB 稠密向量存储"""

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
        self.user_id = user_id
        self._client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"user_id": str(user_id)},
        )

    def add_documents(
        self, docs: list[DocumentUnit], embeddings: list[list[float]]
    ) -> None:
        """添加文档到 ChromaDB"""
        if not docs:
            return

        ids = [doc.document_id for doc in docs]
        texts = [doc.content for doc in docs]
        metadatas = [
            {
                "kb_id": doc.kb_id,
                "file_id": doc.file_id,
                "chunk_index": doc.chunk_index,
                **doc.metadata,
            }
            for doc in docs
        ]

        self._collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )

    def retrieve(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[tuple[DocumentUnit, float]]:
        """检索匹配的文档"""
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=metadata_filter,
        )

        doc_units = []
        for i, (doc_id, text, metadata, distance) in enumerate(
            zip(
                results["ids"][0],
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            )
        ):
            # ChromaDB 返回的是距离，转换为相似度分数
            score = 1.0 - distance if distance is not None else 0.0

            doc_unit = DocumentUnit(
                document_id=doc_id,
                kb_id=metadata.get("kb_id", ""),
                file_id=metadata.get("file_id", ""),
                chunk_index=metadata.get("chunk_index", 0),
                content=text or "",
                metadata=metadata,
            )
            doc_units.append((doc_unit, score))

        return doc_units

    def delete_by_document_ids(self, document_ids: list[str]) -> int:
        """根据 document_id 删除文档"""
        if not document_ids:
            return 0
        self._collection.delete(ids=document_ids)
        return len(document_ids)

    def delete_by_file_id(self, file_id: str) -> int:
        """根据 file_id 删除文档"""
        try:
            results = self._collection.get(where={"file_id": file_id})
            if not results["ids"]:
                return 0
            ids = results["ids"]
            self._collection.delete(ids=ids)
            return len(ids)
        except Exception:
            return 0
```

- [ ] **Step 2: 更新 stores/__init__.py**

```python
"""RAG Stores"""

from app.services.rag.stores.base import DenseStore, DocumentUnit, SparseStore
from app.services.rag.stores.chroma_dense import ChromaDenseStore

__all__ = [
    "DenseStore",
    "SparseStore",
    "DocumentUnit",
    "ChromaDenseStore",
]
```

- [ ] **Step 3: 提交**

```bash
git add app/services/rag/stores/__init__.py app/services/rag/stores/chroma_dense.py
git commit -m "feat(rag): add ChromaDenseStore implementation"
```

---

## Task 3: 创建 stores/pg_dense.py — PGDenseStore

**Files:**
- Create: `app/services/rag/stores/pg_dense.py`
- Modify: `app/services/rag/stores/__init__.py`

**依赖:** SQLAlchemy 2.0 async session, asyncpg, pgvector

- [ ] **Step 1: 编写 PGDenseStore**

```python
"""PostgreSQL + pgvector 稠密向量存储实现"""

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

    def _build_retrieve_sql(self) -> str:
        """构建检索 SQL（余弦相似度）"""
        return f"""
            SELECT id, document_id, kb_id, file_id, chunk_index, content, metadata,
                   1 - (embedding <=> :embedding) AS score
            FROM {self.table_name}
            WHERE kb_id = :kb_id
            ORDER BY embedding <=> :embedding
            LIMIT :top_k
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
        kb_id: str | None = None,
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
                where_clauses.append(f"metadata->>:key = :{key}")
                params[key] = str(value)

        if kb_id:
            where_clauses.append("kb_id = :kb_id")
            params["kb_id"] = kb_id

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
```

- [ ] **Step 2: 更新 stores/__init__.py**

```python
"""RAG Stores"""

from app.services.rag.stores.base import DenseStore, DocumentUnit, SparseStore
from app.services.rag.stores.chroma_dense import ChromaDenseStore
from app.services.rag.stores.pg_dense import PGDenseStore

__all__ = [
    "DenseStore",
    "SparseStore",
    "DocumentUnit",
    "ChromaDenseStore",
    "PGDenseStore",
]
```

- [ ] **Step 3: 提交**

```bash
git add app/services/rag/stores/__init__.py app/services/rag/stores/pg_dense.py
git commit -m "feat(rag): add PGDenseStore implementation"
```

---

## Task 4: 创建 stores/pg_sparse.py — PGSparseStore

**Files:**
- Create: `app/services/rag/stores/pg_sparse.py`
- Modify: `app/services/rag/stores/__init__.py`

**依赖:** jieba 分词，to_tsvector/to_tsquery

- [ ] **Step 1: 编写 PGSparseStore**

```python
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
        kb_id: str | None = None,
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
            for key, value in metadata_filter.items():
                where_clauses.append(f"metadata->>:{key} = :{key}")
                params[key] = str(value)

        if kb_id:
            where_clauses.append("kb_id = :kb_id")
            params["kb_id"] = kb_id

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
```

- [ ] **Step 2: 更新 stores/__init__.py**

```python
"""RAG Stores"""

from app.services.rag.stores.base import DenseStore, DocumentUnit, SparseStore
from app.services.rag.stores.chroma_dense import ChromaDenseStore
from app.services.rag.stores.pg_dense import PGDenseStore
from app.services.rag.stores.pg_sparse import PGSparseStore

__all__ = [
    "DenseStore",
    "SparseStore",
    "DocumentUnit",
    "ChromaDenseStore",
    "PGDenseStore",
    "PGSparseStore",
]
```

- [ ] **Step 3: 提交**

```bash
git add app/services/rag/stores/__init__.py app/services/rag/stores/pg_sparse.py
git commit -m "feat(rag): add PGSparseStore with jieba tokenization"
```

---

## Task 5: 创建 document_loader.py — DocumentLoader

**Files:**
- Create: `app/services/rag/document_loader.py`

**依赖:** langchain_community.document_loaders

- [ ] **Step 1: 编写 DocumentLoader**

```python
"""Document Loader — 支持多种文件类型加载"""

from pathlib import Path
from typing import Any

from langchain_community.document_loaders import (
    CSVLoader,
    DocxLoader,
    JSONLLoader,
    PDFLoader,
    TextLoader,
)
from langchain_core.documents import Document

from app.services.rag.stores.base import DocumentUnit


class DocumentLoader:
    """
    文档加载器，支持多种文件类型

    支持类型：txt, md, pdf, docx, csv, jsonl
    使用注册表模式，按文件扩展名路由到对应加载器
    """

    _LOADER_REGISTRY: dict[str, Any] = {
        ".txt": TextLoader,
        ".md": TextLoader,
        ".pdf": PDFLoader,
        ".docx": DocxLoader,
        ".csv": CSVLoader,
        ".jsonl": JSONLLoader,
    }

    def load(
        self, file_path: str | Path, encoding: str = "utf-8"
    ) -> list[Document]:
        """
        加载文件，返回 LangChain Document 列表

        Args:
            file_path: 文件路径
            encoding: 编码格式

        Returns:
            LangChain Document 列表
        """
        path = Path(file_path)
        ext = path.suffix.lower()

        loader_cls = self._LOADER_REGISTRY.get(ext)
        if not loader_cls:
            raise ValueError(f"Unsupported file type: {ext}")

        # CSVLoader 和 JSONLLoader 需要特殊处理
        if ext == ".csv":
            loader = CSVLoader(file_path=str(path), encoding=encoding)
        elif ext == ".jsonl":
            loader = JSONLLoader(file_path=str(path), encoding=encoding)
        else:
            loader = loader_cls(str(path), encoding=encoding)

        return loader.load()

    def load_with_metadata(
        self,
        file_path: str | Path,
        metadata: dict,
        encoding: str = "utf-8",
    ) -> list[Document]:
        """
        加载文件并合并元数据

        Args:
            file_path: 文件路径
            metadata: 要合并的元数据
            encoding: 编码格式

        Returns:
            包含合并元数据的 LangChain Document 列表
        """
        docs = self.load(file_path, encoding)
        for doc in docs:
            doc.metadata.update(metadata)
        return docs
```

- [ ] **Step 2: 提交**

```bash
git add app/services/rag/document_loader.py
git commit -m "feat(rag): add DocumentLoader with registry pattern"
```

---

## Task 6: 创建 text_splitter.py — TextSplitter

**Files:**
- Create: `app/services/rag/text_splitter.py`

**依赖:** langchain_text_splitters

- [ ] **Step 1: 编写 TextSplitter**

```python
"""Text Splitter — 支持 recursive 和 markdown 两种分块模式"""

from langchain_core.documents import Document
from langchain_text_splitters import (
    MarkdownTextSplitter,
    RecursiveCharacterTextSplitter,
)


class TextSplitter:
    """
    文本分块器

    支持模式：
    - "recursive": RecursiveCharacterTextSplitter，按字符递归分割
    - "markdown": MarkdownTextSplitter，按 Markdown 标题结构分割
    """

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        mode: str = "recursive",
    ) -> None:
        """
        初始化 TextSplitter

        Args:
            chunk_size: 分块大小（字符数）
            chunk_overlap: 分块重叠大小
            mode: 分块模式，"recursive" 或 "markdown"
        """
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if chunk_overlap < 0:
            raise ValueError("chunk_overlap must be non-negative")
        if mode not in ("recursive", "markdown"):
            raise ValueError("mode must be 'recursive' or 'markdown'")

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.mode = mode

    def _get_splitter(self) -> RecursiveCharacterTextSplitter | MarkdownTextSplitter:
        """获取对应的分割器实例"""
        if self.mode == "markdown":
            return MarkdownTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
            )
        else:
            return RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
            )

    def split_documents(self, documents: list[Document]) -> list[Document]:
        """
        分割文档列表

        Args:
            documents: LangChain Document 列表

        Returns:
            分割后的 Document 列表
        """
        splitter = self._get_splitter()
        return splitter.split_documents(documents)

    def split_text(self, text: str) -> list[str]:
        """
        分割单个文本

        Args:
            text: 要分割的文本

        Returns:
            分割后的文本列表
        """
        splitter = self._get_splitter()
        return splitter.split_text(text)
```

- [ ] **Step 2: 提交**

```bash
git add app/services/rag/text_splitter.py
git commit -m "feat(rag): add TextSplitter with recursive and markdown modes"
```

---

## Task 7: 创建 index_service.py — RAGIndexService

**Files:**
- Create: `app/services/rag/index_service.py`

- [ ] **Step 1: 编写 RAGIndexService**

```python
"""RAG Index Service — 文档索引管道"""

import uuid
from pathlib import Path
from typing import Any

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
        # 返回任一结果（理论上两者应该相等）
        return deleted_dense
```

- [ ] **Step 2: 提交**

```bash
git add app/services/rag/index_service.py
git commit -m "feat(rag): add RAGIndexService for document indexing"
```

---

## Task 8: 创建 retrieval_service.py — RAGRetrievalService

**Files:**
- Create: `app/services/rag/retrieval_service.py`

- [ ] **Step 1: 编写 RAGRetrievalService**

```python
"""RAG Retrieval Service — 混合检索和 RAG 管道"""

from typing import Any

from app.services.providers.base import EmbeddingProvider, LLMProvider, RerankerProvider
from app.services.rag.stores.base import DenseStore, DocumentUnit, SparseStore


class RAGRetrievalService:
    """
    RAG 检索服务

    完整检索流程：
    1. 接收用户查询
    2. Query Understanding（Multi-Query 改写）
    3. 多路检索：
       - Vector Search（语义）
       - BM25 Search（关键词）
       - Metadata Filter（过滤）
    4. RRF 融合结果
    5. Reranker 精排（Cross Encoder，可选）
    6. Context 构建（合并 / 去重 / 压缩）
    7. LLM 生成答案（可选）
    """

    def __init__(
        self,
        dense_store: DenseStore,
        sparse_store: SparseStore,
        embedding_provider: EmbeddingProvider,
        reranker_provider: RerankerProvider | None = None,
        llm_provider: LLMProvider | None = None,
    ) -> None:
        self.dense_store = dense_store
        self.sparse_store = sparse_store
        self.embedding_provider = embedding_provider
        self.reranker_provider = reranker_provider
        self.llm_provider = llm_provider

    # ===================================================================
    # Query Understanding
    # ===================================================================

    def _expand_query(self, query: str, n: int = 1) -> list[str]:
        """
        查询扩展

        Args:
            query: 原始查询
            n: 生成查询数量，n=1 时直接短路

        Returns:
            扩展后的查询列表
        """
        if n <= 1:
            return [query]

        if not self.llm_provider:
            return [query]

        # Multi-Query 改写提示词
        prompt = f"""你是一个查询改写助手。请将以下查询改写为 {n} 个不同的表达方式，
        每个表达方式都应该保持原意但使用不同的词汇和句式。
        直接输出{n}个查询，用换行分隔，不要加序号。

        原查询：{query}"""

        response = self.llm_provider.achat([
            {"role": "user", "content": prompt}
        ])

        queries = [q.strip() for q in response.split("\n") if q.strip()]
        return queries[:n] if queries else [query]

    # ===================================================================
    # Hybrid Retrieval
    # ===================================================================

    def _dense_retrieve(
        self,
        query_embedding: list[float],
        top_k: int,
        metadata_filter: dict[str, Any] | None = None,
        kb_id: str | None = None,
    ) -> list[tuple[DocumentUnit, float]]:
        """稠密检索"""
        return self.dense_store.retrieve(
            query_embedding=query_embedding,
            top_k=top_k,
            metadata_filter=metadata_filter,
        )

    def _sparse_retrieve(
        self,
        query: str,
        top_k: int,
        metadata_filter: dict[str, Any] | None = None,
        kb_id: str | None = None,
    ) -> list[tuple[DocumentUnit, float]]:
        """稀疏检索"""
        return self.sparse_store.retrieve(
            query=query,
            top_k=top_k,
            metadata_filter=metadata_filter,
        )

    def _rrf_fusion(
        self,
        dense_results: list[tuple[DocumentUnit, float]],
        sparse_results: list[tuple[DocumentUnit, float]],
        vector_weight: float = 0.7,
        k: int = 60,
    ) -> list[tuple[DocumentUnit, float]]:
        """
        RRF (Reciprocal Rank Fusion) 融合

        Formula: RRF_score(doc) = Σ weight_i × 1/(k + rank_i(doc))

        Args:
            dense_results: 稠密检索结果
            sparse_results: 稀疏检索结果
            vector_weight: 稠密权重 (sparse_weight = 1 - vector_weight)
            k: RRF 常数（默认 60）

        Returns:
            融合后的结果列表
        """
        doc_scores: dict[str, float] = {}
        doc_units: dict[str, DocumentUnit] = {}

        # 归一化分数到 [0, 1]
        def normalize(scores: list[float]) -> list[float]:
            if not scores:
                return []
            min_s, max_s = min(scores), max(scores)
            if max_s == min_s:
                return [1.0] * len(scores)
            return [(s - min_s) / (max_s - min_s) for s in scores]

        # Dense scores
        dense_scores = normalize([s for _, s in dense_results])
        for i, (doc, _) in enumerate(dense_results):
            doc_id = doc.document_id
            doc_units[doc_id] = doc
            if doc_id not in doc_scores:
                doc_scores[doc_id] = 0.0
            doc_scores[doc_id] += vector_weight * (1 / (k + i + 1)) * dense_scores[i]

        # Sparse scores
        sparse_scores = normalize([s for _, s in sparse_results])
        sparse_weight = 1 - vector_weight
        for i, (doc, _) in enumerate(sparse_results):
            doc_id = doc.document_id
            doc_units[doc_id] = doc
            if doc_id not in doc_scores:
                doc_scores[doc_id] = 0.0
            doc_scores[doc_id] += sparse_weight * (1 / (k + i + 1)) * sparse_scores[i]

        # 排序
        sorted_docs = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)
        return [(doc_units[doc_id], score) for doc_id, score in sorted_docs]

    async def hybrid_retrieve(
        self,
        query: str,
        top_k: int = 10,
        vector_weight: float = 0.7,
        metadata_filter: dict[str, Any] | None = None,
        n_queries: int = 1,
        kb_id: str | None = None,
    ) -> list[DocumentUnit]:
        """
        混合检索（稠密 + 稀疏 + RRF 融合）

        Args:
            query: 查询文本
            top_k: 返回数量
            vector_weight: 稠密权重
            metadata_filter: 元数据过滤（同时作用于两个 store）
            n_queries: Multi-Query 数量，n=1 时不调用 LLM
            kb_id: 知识库 ID

        Returns:
            DocumentUnit 列表
        """
        # 1. Query Understanding
        queries = self._expand_query(query, n=n_queries)

        all_fused_results: list[tuple[DocumentUnit, float]] = []

        for q in queries:
            # 2. Embed query for dense search
            query_embedding = await self.embedding_provider.aembed_query(q)

            # 3. 并行检索
            dense_results = self._dense_retrieve(
                query_embedding, top_k, metadata_filter, kb_id
            )
            sparse_results = self._sparse_retrieve(
                q, top_k, metadata_filter, kb_id
            )

            # 4. RRF 融合
            fused = self._rrf_fusion(dense_results, sparse_results, vector_weight)
            all_fused_results.extend(fused)

        # 5. 去重（按 document_id）
        seen = set()
        unique_results = []
        for doc, score in all_fused_results:
            if doc.document_id not in seen:
                seen.add(doc.document_id)
                unique_results.append((doc, score))

        # 6. 按 score 排序并截取
        unique_results.sort(key=lambda x: x[1], reverse=True)
        return [doc for doc, _ in unique_results[:top_k]]

    # ===================================================================
    # Reranking
    # ===================================================================

    async def rerank(
        self,
        query: str,
        documents: list[DocumentUnit],
        top_k: int = 3,
    ) -> list[DocumentUnit]:
        """重排（Cross-Encoder）"""
        if not self.reranker_provider or len(documents) <= 1:
            return documents[:top_k]

        docs_texts = [doc.content for doc in documents]
        reranked = await self.reranker_provider.arerank(
            query=query,
            documents=docs_texts,
            top_n=top_k,
        )

        # Map back
        doc_map = {doc.content: doc for doc in documents}
        result = []
        for item in reranked:
            doc_text = item.get("document", "")
            if doc_text in doc_map:
                result.append(doc_map[doc_text])
        return result

    # ===================================================================
    # Context Building
    # ===================================================================

    def build_context(
        self,
        documents: list[DocumentUnit],
        max_length: int = 4000,
    ) -> str:
        """
        构建上下文

        Args:
            documents: 文档列表
            max_length: 最大长度

        Returns:
            上下文字符串
        """
        context_parts = []
        current_length = 0

        for i, doc in enumerate(documents, 1):
            source_info = ""
            if doc.metadata.get("file_name"):
                source_info = f" [{doc.metadata['file_name']}]"

            part = f"[{i}]{source_info}\n{doc.content}"
            if current_length + len(part) > max_length:
                break
            context_parts.append(part)
            current_length += len(part)

        return "\n\n".join(context_parts)

    # ===================================================================
    # Generation
    # ===================================================================

    _default_prompt = """你是一个问答助手。请根据以下参考资料回答用户的问题。
参考资料：{context}
用户问题：{question}
请基于参考资料给出准确、详细的回答。如果参考资料中没有相关信息，请说明无法回答。"""

    async def generate(
        self,
        query: str,
        documents: list[DocumentUnit],
        prompt_template: str | None = None,
        conversation_history: list[dict] | None = None,
    ) -> str:
        """生成答案"""
        if not self.llm_provider:
            raise ValueError("LLM provider not configured")

        context = self.build_context(documents)
        prompt = (prompt_template or self._default_prompt).format(
            context=context,
            question=query,
        )

        messages = []
        if conversation_history:
            for turn in conversation_history[-3:]:
                messages.append({"role": "user", "content": turn.get("question", "")})
                messages.append({"role": "assistant", "content": turn.get("answer", "")})
        messages.append({"role": "user", "content": prompt})

        return await self.llm_provider.achat(messages)

    # ===================================================================
    # Full RAG Pipeline
    # ===================================================================

    async def rag(
        self,
        query: str,
        top_k: int = 5,
        vector_weight: float = 0.7,
        metadata_filter: dict[str, Any] | None = None,
        enable_rerank: bool = True,
        rerank_top_k: int = 3,
        n_queries: int = 1,
        prompt_template: str | None = None,
        conversation_history: list[dict] | None = None,
        kb_id: str | None = None,
    ) -> tuple[str, list[DocumentUnit], list[str]]:
        """
        完整 RAG 流程

        Args:
            query: 查询
            top_k: 检索数量
            vector_weight: 稠密权重
            metadata_filter: 元数据过滤
            enable_rerank: 是否重排
            rerank_top_k: 重排后返回数量
            n_queries: Multi-Query 数量
            prompt_template: 提示词模板
            conversation_history: 对话历史
            kb_id: 知识库 ID

        Returns:
            (answer, documents, sources)
        """
        # 1. Hybrid Retrieval
        documents = await self.hybrid_retrieve(
            query=query,
            top_k=top_k,
            vector_weight=vector_weight,
            metadata_filter=metadata_filter,
            n_queries=n_queries,
            kb_id=kb_id,
        )

        # 2. Reranking
        if enable_rerank:
            documents = await self.rerank(query, documents, rerank_top_k)
        else:
            documents = documents[:rerank_top_k]

        # 3. Generation
        sources = list({
            doc.metadata.get("file_name", "Unknown")
            for doc in documents
            if doc.metadata.get("file_name")
        })

        if self.llm_provider:
            answer = await self.generate(
                query=query,
                documents=documents,
                prompt_template=prompt_template,
                conversation_history=conversation_history,
            )
        else:
            answer = "\n\n".join(
                [f"[Score: {doc.metadata.get('score', 0.0):.3f}] {doc.content[:200]}..."
                 for doc in documents]
            )

        return answer, documents, sources
```

- [ ] **Step 2: 提交**

```bash
git add app/services/rag/retrieval_service.py
git commit -m "feat(rag): add RAGRetrievalService with hybrid search and RRF fusion"
```

---

## Task 9: 更新 service_factory.py — 添加工厂函数

**Files:**
- Modify: `app/services/rag/service_factory.py`

- [ ] **Step 1: 更新 service_factory.py**

在文件开头添加导入，然后在文件末尾添加新的工厂函数。

```python
"""
Service Factory - Creates RAG service from Knowledge Base configuration.

Provides factory functions to create RAGIndexService and RAGRetrievalService
instances with proper embedding/reranker/vector providers based on KB model configuration.
"""

# ... 保留现有导入 ...

# 新增导入
from app.services.rag.index_service import RAGIndexService
from app.services.rag.retrieval_service import RAGRetrievalService
from app.services.rag.stores.chroma_dense import ChromaDenseStore
from app.services.rag.stores.pg_dense import PGDenseStore
from app.services.rag.stores.pg_sparse import PGSparseStore


async def create_rag_index_service(
    kb: KbDocument,
    embedding_provider: EmbeddingProvider,
    db_session: AsyncSession,
    vector_db_type: str = "chromadb",  # "chromadb" | "postgresql"
) -> RAGIndexService:
    """
    创建 RAG 索引服务

    Args:
        kb: 知识库配置
        embedding_provider: 嵌入提供者
        db_session: 数据库会话
        vector_db_type: 向量数据库类型，"chromadb" 或 "postgresql"

    Returns:
        RAGIndexService 实例
    """
    if vector_db_type == "chromadb":
        settings = get_settings()
        dense_store: DenseStore = ChromaDenseStore(
            embedding_provider=embedding_provider,
            persist_directory=str(settings.CHROMA_PERSIST_DIR),
            collection_name=kb.collection_name,
            user_id=kb.user_id,
        )
    else:  # postgresql
        dense_store = PGDenseStore(
            db_session=db_session,
            embedding_provider=embedding_provider,
        )

    sparse_store = PGSparseStore(db_session=db_session)

    return RAGIndexService(
        dense_store=dense_store,
        sparse_store=sparse_store,
        embedding_provider=embedding_provider,
    )


async def create_rag_retrieval_service(
    kb: KbDocument,
    embedding_provider: EmbeddingProvider,
    db_session: AsyncSession,
    reranker_provider: RerankerProvider | None = None,
    llm_provider: LLMProvider | None = None,
    vector_db_type: str = "chromadb",
) -> RAGRetrievalService:
    """
    创建 RAG 检索服务

    Args:
        kb: 知识库配置
        embedding_provider: 嵌入提供者
        db_session: 数据库会话
        reranker_provider: 重排提供者
        llm_provider: LLM 提供者
        vector_db_type: 向量数据库类型

    Returns:
        RAGRetrievalService 实例
    """
    if vector_db_type == "chromadb":
        settings = get_settings()
        dense_store: DenseStore = ChromaDenseStore(
            embedding_provider=embedding_provider,
            persist_directory=str(settings.CHROMA_PERSIST_DIR),
            collection_name=kb.collection_name,
            user_id=kb.user_id,
        )
    else:
        dense_store = PGDenseStore(
            db_session=db_session,
            embedding_provider=embedding_provider,
        )

    sparse_store = PGSparseStore(db_session=db_session)

    return RAGRetrievalService(
        dense_store=dense_store,
        sparse_store=sparse_store,
        embedding_provider=embedding_provider,
        reranker_provider=reranker_provider,
        llm_provider=llm_provider,
    )
```

- [ ] **Step 2: 提交**

```bash
git add app/services/rag/service_factory.py
git commit -m "feat(rag): add create_rag_index_service and create_rag_retrieval_service factories"
```

---

## Task 10: 更新 __init__.py — 导出新类

**Files:**
- Modify: `app/services/rag/__init__.py`

- [ ] **Step 1: 更新 __init__.py**

```python
"""RAG Services"""

from app.services.rag.index_service import RAGIndexService
from app.services.rag.retrieval_service import RAGRetrievalService
from app.services.rag.stores.base import DenseStore, DocumentUnit, SparseStore
from app.services.rag.stores.chroma_dense import ChromaDenseStore
from app.services.rag.stores.pg_dense import PGDenseStore
from app.services.rag.stores.pg_sparse import PGSparseStore

__all__ = [
    # Core abstractions
    "DenseStore",
    "SparseStore",
    "DocumentUnit",
    # Store implementations
    "ChromaDenseStore",
    "PGDenseStore",
    "PGSparseStore",
    # Services
    "RAGIndexService",
    "RAGRetrievalService",
]
```

- [ ] **Step 2: 提交**

```bash
git add app/services/rag/__init__.py
git commit -m "feat(rag): export new store and service classes"
```

---

## Task 11: 删除 design.py

**Files:**
- Delete: `app/services/rag/design.py`

- [ ] **Step 1: 删除 design.py 并提交**

```bash
rm app/services/rag/design.py
git add -A
git commit -m "refactor(rag): remove design.py after implementation"
```

---

## 自检清单

完成所有任务后，检查以下内容：

1. **Spec coverage:**
   - [x] DenseStore (ABC) — Task 1
   - [x] SparseStore (ABC) — Task 1
   - [x] DocumentUnit — Task 1
   - [x] ChromaDenseStore — Task 2
   - [x] PGDenseStore — Task 3
   - [x] PGSparseStore — Task 4
   - [x] DocumentLoader — Task 5
   - [x] TextSplitter — Task 6
   - [x] RAGIndexService — Task 7
   - [x] RAGRetrievalService — Task 8
   - [x] create_rag_index_service — Task 9
   - [x] create_rag_retrieval_service — Task 9
   - [x] design.py 删除 — Task 11

2. **Type consistency:**
   - DenseStore.retrieve() 的参数：`query_embedding: list[float]`（不是 query str）
   - SparseStore.retrieve() 的参数：`query: str`（不是 query_embedding）
   - DocumentUnit.document_id 用于关联两个 store

3. **依赖检查:**
   - chromadb >= 1.5.5 ✓
   - pgvector >= 0.4.2 ✓
   - jieba >= 0.42.1 ✓
   - langchain-community >= 0.4.1 ✓
   - langchain-text-splitters >= 1.1.1 ✓

# RAG Service 详细设计文档

## 一、架构概览

```
RAGIndexService
├── DocumentLoader (txt/md/pdf/docx/csv/jsonl)
├── TextSplitter (recursive | markdown)
├── EmbeddingProvider
├── DenseStore
│   ├── ChromaDenseStore (ChromaDB)
│   └── PGDenseStore (PostgreSQL + pgvector)
└── SparseStore
    └── PGSparseStore (PostgreSQL + jieba + to_tsvector)

RAGRetrievalService
├── DenseStore
├── SparseStore
├── EmbeddingProvider
├── RerankerProvider (optional)
├── LLMProvider (optional, for multi-query rewrite)
└── RRF fusion (k=60)
```

### 与现有 RAGService 的关系

- 现有 `RAGService` (rag_service.py) 保持不变，继续使用 ChromaDB
- 新设计通过 `create_rag_index_service()` / `create_rag_retrieval_service()` 工厂函数创建实例
- 新设计支持 PostgreSQL + pgvector 作为 ChromaDB 的替代方案

---

## 二、核心数据结构

### 2.1 DocumentUnit

```python
class DocumentUnit(BaseModel):
    """RAG 模块/服务中循环流通的数据结构"""
    document_id: str          # 外部生成的 UUID
    kb_id: str
    file_id: str
    chunk_index: int
    content: str              # 原始文本
    metadata: dict = {}       # 额外元数据
```

### 2.2 DenseStore (ABC)

```python
class DenseStore(ABC):
    """稠密向量存储抽象基类"""

    @abstractmethod
    def add_documents(self, docs: list[DocumentUnit], embeddings: list[list[float]]) -> None:
        """添加文档到稠密存储"""
        pass

    @abstractmethod
    def retrieve(
        self,
        query: str,
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
```

### 2.3 SparseStore (ABC)

```python
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

---

## 三、存储实现

### 3.1 ChromaDenseStore

基于 ChromaDB 的稠密向量存储实现。

**文件：** `app/services/rag/stores/chroma_dense.py`

```python
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
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        self.user_id = user_id
        self._client = chromadb.PersistentClient(path=str(persist_directory))
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"user_id": user_id}
        )
```

### 3.2 PGDenseStore

基于 PostgreSQL + pgvector 的稠密向量存储实现。

**文件：** `app/services/rag/stores/pg_dense.py`

**数据库 Schema：**

```sql
CREATE TABLE pg_chunks (
    id VARCHAR(64) PRIMARY KEY,
    document_id VARCHAR(64) NOT NULL,
    kb_id VARCHAR(64) NOT NULL,
    file_id VARCHAR(64) NOT NULL,
    chunk_index INT NOT NULL,
    content TEXT NOT NULL,
    embedding VECTOR(%s),  -- 动态维度
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_pg_chunks_document_id ON pg_chunks(document_id);
CREATE INDEX idx_pg_chunks_kb_id ON pg_chunks(kb_id);
CREATE INDEX idx_pg_chunks_embedding ON pg_chunks USING IVFFlat (embedding vector_cosine_ops);
```

```python
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
```

### 3.3 PGSparseStore

基于 PostgreSQL + jieba + to_tsvector 的稀疏存储实现。

**文件：** `app/services/rag/stores/pg_sparse.py`

**数据库 Schema：**

```sql
CREATE TABLE pg_sparse_chunks (
    id VARCHAR(64) PRIMARY KEY,
    document_id VARCHAR(64) NOT NULL,
    kb_id VARCHAR(64) NOT NULL,
    file_id VARCHAR(64) NOT NULL,
    chunk_index INT NOT NULL,
    content TEXT NOT NULL,
    tokens TEXT NOT NULL,  -- jieba 分词后的 token，空格分隔
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_pg_sparse_document_id ON pg_sparse_chunks(document_id);
CREATE INDEX idx_pg_sparse_tokens ON pg_sparse_chunks USING GIN (to_tsvector('simple', tokens));
```

**核心逻辑：**

- **写入时：** 使用 jieba 对 `content` 分词，结果存入 `tokens` 字段
- **检索时：** 查询也用 jieba 分词，然后 `to_tsquery('simple', tokens)` 匹配
- **关联：** `document_id` 与 `DenseStore` 共用，实现混合检索

```python
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
        import jieba
        return " ".join(jieba.cut(text))
```

---

## 四、DocumentLoader

### 4.1 设计

使用注册表模式（Registry Pattern）支持多种文件类型。

**文件：** `app/services/rag/document_loader.py`

```python
from langchain_core.documents import Document

class DocumentLoader:
    """
    文档加载器，支持多种文件类型

    支持类型：txt, md, pdf, docx, csv, jsonl
    使用注册表模式，按文件扩展名路由到对应加载器
    """

    _LOADER_REGISTRY: dict[str, type[BaseLoader]] = {
        ".txt": TextLoader,
        ".md": TextLoader,
        ".pdf": PDFLoader,
        ".docx": DocxLoader,
        ".csv": CSVLoader,
        ".jsonl": JSONLLoader,
    }

    def load(self, file_path: str | Path, encoding: str = "utf-8") -> list[Document]:
        """加载文件，返回 LangChain Document 列表"""
        path = Path(file_path)
        ext = path.suffix.lower()

        loader_cls = self._LOADER_REGISTRY.get(ext)
        if not loader_cls:
            raise ValueError(f"Unsupported file type: {ext}")

        loader = loader_cls(file_path=str(path), encoding=encoding)
        return loader.load()

    def load_with_metadata(
        self,
        file_path: str | Path,
        metadata: dict,
        encoding: str = "utf-8",
    ) -> list[Document]:
        """加载文件并合并元数据"""
        docs = self.load(file_path, encoding)
        for doc in docs:
            doc.metadata.update(metadata)
        return docs
```

### 4.2 支持的文件类型

| 扩展名 | 加载器 | 说明 |
|--------|--------|------|
| .txt | TextLoader | 纯文本文件 |
| .md | TextLoader | Markdown 文件 |
| .pdf | PDFLoader | PDF 文件（langchain-community） |
| .docx | DocxLoader | Word 文档（langchain-community） |
| .csv | CSVLoader | CSV 文件（按行分割） |
| .jsonl | JSONLLoader | JSON Lines（每行一个 JSON） |

---

## 五、TextSplitter

### 5.1 设计

支持两种分块模式：recursive 和 markdown。

**文件：** `app/services/rag/text_splitter.py`

```python
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter, MarkdownTextSplitter

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
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.mode = mode

    def split_documents(
        self,
        documents: list[Document],
    ) -> list[Document]:
        """分割文档列表"""
        if self.mode == "markdown":
            splitter = MarkdownTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
            )
        else:
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
            )
        return splitter.split_documents(documents)

    def split_text(self, text: str) -> list[str]:
        """分割单个文本"""
        if self.mode == "markdown":
            splitter = MarkdownTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
            )
        else:
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
            )
        return splitter.split_text(text)
```

---

## 六、RAGIndexService

### 6.1 设计

```python
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
        metadata: dict | None = None,
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
        """删除文档"""
        deleted_dense = self.dense_store.delete_by_file_id(file_id)
        deleted_sparse = self.sparse_store.delete_by_file_id(file_id)
        return deleted_dense
```

---

## 七、RAGRetrievalService

### 7.1 设计

```python
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
        return queries[:n]

    # ===================================================================
    # Hybrid Retrieval
    # ===================================================================

    def _dense_retrieve(
        self,
        query_embedding: list[float],
        top_k: int,
        metadata_filter: dict | None,
    ) -> list[tuple[DocumentUnit, float]]:
        """稠密检索"""
        return self.dense_store.retrieve(
            query="",
            query_embedding=query_embedding,
            top_k=top_k,
            metadata_filter=metadata_filter,
        )

    def _sparse_retrieve(
        self,
        query: str,
        top_k: int,
        metadata_filter: dict | None,
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
        metadata_filter: dict | None = None,
        n_queries: int = 1,
    ) -> list[DocumentUnit]:
        """
        混合检索（稠密 + 稀疏 + RRF 融合）

        Args:
            query: 查询文本
            top_k: 返回数量
            vector_weight: 稠密权重
            metadata_filter: 元数据过滤（同时作用于两个 store）
            n_queries: Multi-Query 数量，n=1 时不调用 LLM

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
            dense_results = self._dense_retrieve(query_embedding, top_k, metadata_filter)
            sparse_results = self._sparse_retrieve(q, top_k, metadata_filter)

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
        metadata_filter: dict | None = None,
        enable_rerank: bool = True,
        rerank_top_k: int = 3,
        n_queries: int = 1,
        prompt_template: str | None = None,
        conversation_history: list[dict] | None = None,
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

---

## 八、Service Factory

### 8.1 设计

**文件：** `app/services/rag/service_factory.py`

```python
from app.modules.knowledge_base.models import KbDocument
from app.services.providers.base import EmbeddingProvider, LLMProvider, RerankerProvider

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
        vector_db_type: 向量数据库类型

    Returns:
        RAGIndexService 实例
    """
    if vector_db_type == "chromadb":
        from app.services.rag.stores.chroma_dense import ChromaDenseStore
        from app.services.rag.stores.pg_sparse import PGSparseStore
        from app.core.settings import get_settings

        settings = get_settings()
        dense_store = ChromaDenseStore(
            embedding_provider=embedding_provider,
            persist_directory=str(settings.CHROMA_PERSIST_DIR),
            collection_name=kb.collection_name,
            user_id=kb.user_id,
        )
        sparse_store = PGSparseStore(db_session=db_session)
    else:  # postgresql
        from app.services.rag.stores.pg_dense import PGDenseStore
        from app.services.rag.stores.pg_sparse import PGSparseStore

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
        from app.services.rag.stores.chroma_dense import ChromaDenseStore
        from app.services.rag.stores.pg_sparse import PGSparseStore
        from app.core.settings import get_settings

        settings = get_settings()
        dense_store = ChromaDenseStore(
            embedding_provider=embedding_provider,
            persist_directory=str(settings.CHROMA_PERSIST_DIR),
            collection_name=kb.collection_name,
            user_id=kb.user_id,
        )
        sparse_store = PGSparseStore(db_session=db_session)
    else:
        from app.services.rag.stores.pg_dense import PGDenseStore
        from app.services.rag.stores.pg_sparse import PGSparseStore

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

---

## 九、文件结构

```
app/services/rag/
├── __init__.py
├── rag_service.py           # 现有服务（保持不变）
├── service_factory.py       # 更新：添加 create_rag_index_service, create_rag_retrieval_service
├── document_loader.py       # 新：DocumentLoader
├── text_splitter.py         # 新/更新：TextSplitter
├── index_service.py         # 新：RAGIndexService
├── retrieval_service.py     # 新：RAGRetrievalService
└── stores/
    ├── __init__.py
    ├── base.py              # 新：DenseStore (ABC), SparseStore (ABC), DocumentUnit
    ├── chroma_dense.py      # 新：ChromaDenseStore
    ├── pg_dense.py          # 新：PGDenseStore
    └── pg_sparse.py         # 新：PGSparseStore
```

---

## 十、关键设计决策总结

| 决策点 | 方案 |
|--------|------|
| DenseStore 实现 | ChromaDenseStore + PGDenseStore |
| SparseStore 实现 | 仅 PGSparseStore (PostgreSQL BM25) |
| DocumentLoader | txt/md/pdf/docx/csv/jsonl |
| TextSplitter | recursive + markdown 两种模式 |
| Multi-Query | n=1 短路不调用 LLM，n>1 调用 LLM 改写 |
| metadata_filter | 同时作用于 DenseStore 和 SparseStore |
| RRF k | 硬编码 60 |
| document_id | RAGIndexService 生成 UUID，传入各 store |
| 写入时分词 | jieba 在 PGSparseStore.add_documents() 内部处理 |

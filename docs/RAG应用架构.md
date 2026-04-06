# RAG 应用架构文档

> 本文档详细描述 RAG（Retrieval-Augmented Generation）系统的架构设计，包括层次结构、组件关系、数据流和依赖管理。

---

## 目录

1. [系统概述](#1-系统概述)
2. [架构层次模型](#2-架构层次模型)
3. [层次详解与依赖关系](#3-层次详解与依赖关系)
4. [核心数据流](#4-核心数据流)
5. [核心数据结构](#5-核心数据结构)
6. [关键设计模式](#6-关键设计模式)
7. [组件关系图](#7-组件关系图)
8. [关键文件索引](#8-关键文件索引)

---

## 1. 系统概述

### 1.1 RAG 系统定位

RAG 系统是 AI Studio 的核心能力模块，负责：

- **文档索引**：将用户上传的文档转化为可检索的知识
- **混合检索**：结合稠密向量检索与稀疏关键词检索
- **智能排序**：RRF 融合 + Rerank 精排
- **增强生成**：基于检索结果生成准确答案

### 1.2 核心能力

| 能力 | 说明 |
|------|------|
| 多格式文档支持 | PDF, DOCX, TXT, MD, CSV, JSON |
| 文本分块 | Recursive 模式 / Markdown 模式 |
| 稠密向量检索 | ChromaDB / PostgreSQL + pgvector |
| 稀疏关键词检索 | PostgreSQL + FTS + jieba 分词 |
| RRF 融合 | Reciprocal Rank Fusion 多路召回融合 |
| 重排 | Cross-Encoder Reranker |
| LLM 生成 | OpenAI 兼容接口调用 |

---

## 2. 架构层次模型

### 2.1 层次总览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              应用层 (Application)                           │
│  KnowledgeBaseService：业务编排、配置管理、知识库 CRUD                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                            RAG 服务层 (RAG Service)                         │
│  ┌──────────────────────┐          ┌──────────────────────┐              │
│  │   RAGIndexService    │          │ RAGRetrievalService  │              │
│  │   文档索引管道        │          │  混合检索 + 生成      │              │
│  └──────────────────────┘          └──────────────────────┘              │
├─────────────────────────────────────────────────────────────────────────────┤
│                          模型接入层 (Model Access)                          │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐               │
│  │ LLMProvider    │  │ EmbeddingProv. │  │ RerankerProv.  │               │
│  └────────────────┘  └────────────────┘  └────────────────┘               │
│                    model_factory.py (工厂函数 + LRU 缓存)                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                          服务组件层 (Service Components)                     │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐      │
│  │DocumentLoader│ │ TextSplitter │ │ DenseStore   │ │ SparseStore  │      │
│  │ 多格式加载    │ │  文本分块    │ │  (ABC)       │ │  (ABC)       │      │
│  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘      │
├─────────────────────────────────────────────────────────────────────────────┤
│                            存储层 (Storage)                                │
│  ┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────────────┐   │
│  │ ChromaDenseStore    │ │ PGDenseStore        │ │ PGSparseStore       │   │
│  │ (ChromaDB 向量存储) │ │ (PG+pgvector)       │ │ (PG+FTS+jieba)     │   │
│  └─────────────────────┘ └─────────────────────┘ └─────────────────────┘   │
├─────────────────────────────────────────────────────────────────────────────┤
│                           基础层 (Infrastructure)                          │
│  PostgreSQL │ Redis │ ChromaDB │ httpx.AsyncClient                         │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 层次职责概览

| 层次 | 职责 | 组件 |
|------|------|------|
| 应用层 | 业务编排、知识库配置管理 | `KnowledgeBaseService` |
| RAG 服务层 | 核心 RAG 逻辑：索引管道、混合检索、生成 | `RAGIndexService`, `RAGRetrievalService` |
| 模型接入层 | 统一模型调用接口、实例缓存 | `Factory`, `LLMProvider`, `EmbeddingProvider`, `RerankerProvider` |
| 服务组件层 | 数据处理、存储抽象 | `DocumentLoader`, `TextSplitter`, `DenseStore`, `SparseStore` |
| 存储层 | 数据持久化 | ChromaDB, PostgreSQL/pgvector, PostgreSQL/FTS |

---

## 3. 层次详解与依赖关系

### 3.1 应用层 (Application Layer)

**职责**：业务编排、知识库配置管理、权限校验

**代表组件**：`KnowledgeBaseService`

**位置**：`app/modules/knowledge_base/service.py`

**依赖关系**：
- 被依赖：Router 层
- 依赖：RAG 服务层

```python
class KnowledgeBaseService:
    """
    应用层服务
    
    职责：
    1. 知识库 CRUD（验证权限、配置校验）
    2. 调用 RAGIndexService 索引文档
    3. 调用 RAGRetrievalService 执行检索
    4. 配置管理和验证
    """
    
    def __init__(self, repo: KnowledgeBaseRepository, ...):
        self.repo = repo
    
    async def retrieve(self, kb_id: str, query: str, user_id: int, ...):
        # 1. 验证 KB 存在性和用户权限
        kb = await self._get_kb_or_raise(kb_id, user_id)
        
        # 2. 调用 RAGRetrievalService
        rag_service = await create_rag_retrieval_service(kb, ...)
        
        # 3. 执行检索
        results = await rag_service.retrieve(...)
        return results
```

**调用关系图**：

```
Router
   │
   ▼
KnowledgeBaseService (应用层)
   │
   ├──► create_rag_index_service()     ──► RAGIndexService
   │
   └──► create_rag_retrieval_service()  ──► RAGRetrievalService
```

---

### 3.2 RAG 服务层 (RAG Service Layer)

**职责**：核心 RAG 逻辑实现

#### 3.2.1 RAGIndexService - 索引管道

**位置**：`app/services/rag/index_service.py`

**职责**：将文档文件转化为可检索的向量数据

```python
class RAGIndexService:
    """
    RAG 索引服务
    
    索引流程：
    file → DocumentLoader → chunks → Embedding → DenseStore
                                              → SparseStore
    """
    
    def __init__(
        self,
        dense_store: DenseStore,
        sparse_store: SparseStore,
        embedding_provider: EmbeddingProvider,
        document_loader: DocumentLoader | None = None,
        text_splitter: TextSplitter | None = None,
    ):
        self.dense_store = dense_store
        self.sparse_store = sparse_store
        self.embedding_provider = embedding_provider
        self.document_loader = document_loader or DocumentLoader()
        self.text_splitter = text_splitter or TextSplitter()
    
    async def index_document(self, file_path, kb_id, file_id, user_id, metadata):
        # 1. 加载文档
        docs = self.document_loader.load_with_metadata(file_path, metadata)
        
        # 2. 分块
        chunks = self.text_splitter.split_documents(docs)
        
        # 3. 生成 DocumentUnit
        doc_units = [DocumentUnit(...) for chunk in chunks]
        
        # 4. 写入向量存储（稠密）
        await self.dense_store.add_documents(doc_units)
        
        # 5. 写入稀疏存储
        await self.sparse_store.add_documents(doc_units)
```

**依赖关系**：
- 依赖：服务组件层（DocumentLoader, TextSplitter, DenseStore, SparseStore）
- 依赖：模型接入层（EmbeddingProvider）

#### 3.2.2 RAGRetrievalService - 混合检索

**位置**：`app/services/rag/retrieval_service.py`

**职责**：执行混合检索、RRF 融合、Rerank、LLM 生成

```python
class RAGRetrievalService:
    """
    RAG 检索服务
    
    完整检索流程：
    1. Query Understanding（Multi-Query 改写）
    2. 多路检索：
       - Vector Search（稠密语义）
       - BM25 Search（稀疏关键词）
    3. RRF 融合
    4. Reranker 精排
    5. Context 构建
    6. LLM 生成答案
    """
    
    def __init__(
        self,
        dense_store: DenseStore,
        sparse_store: SparseStore,
        embedding_provider: EmbeddingProvider,
        reranker_provider: RerankerProvider | None = None,
        llm_provider: LLMProvider | None = None,
    ):
        self.dense_store = dense_store
        self.sparse_store = sparse_store
        self.embedding_provider = embedding_provider
        self.reranker_provider = reranker_provider
        self.llm_provider = llm_provider
    
    async def hybrid_retrieve(self, query, top_k, vector_weight, metadata_filter):
        # 1. Query Understanding
        queries = await self._expand_query(query, n=n_queries)
        
        # 2. 并行检索
        all_results = []
        for q in queries:
            query_emb = await self.embedding_provider.aembed_query(q)
            
            # 稠密 + 稀疏并行
            dense_results, sparse_results = await asyncio.gather(
                self.dense_store.retrieve(query_emb, top_k, metadata_filter),
                self.sparse_store.retrieve(q, top_k, metadata_filter),
            )
            
            # 3. RRF 融合
            fused = self._rrf_fusion(dense_results, sparse_results, vector_weight)
            all_results.extend(fused)
        
        # 4. 去重 + 排序
        return [doc for doc, _ in unique_and_sort(all_results)][:top_k]
    
    async def rag(self, query, top_k, ...):
        # 完整 RAG 流程
        documents = await self.hybrid_retrieve(...)
        
        if self.reranker_provider:
            documents = await self.rerank(query, documents, rerank_top_k)
        
        if self.llm_provider:
            answer = await self.generate(query, documents, ...)
        else:
            answer = self.build_context(documents)
        
        return answer, documents, sources
```

**依赖关系**：
- 依赖：服务组件层（DenseStore, SparseStore）
- 依赖：模型接入层（EmbeddingProvider, RerankerProvider, LLMProvider）

**RAG 服务层依赖图**：

```
┌──────────────────────────────────────────────────────────────┐
│                     RAG 服务层                               │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────────┐      ┌──────────────────────┐     │
│  │   RAGIndexService   │      │ RAGRetrievalService  │     │
│  └──────────┬──────────┘      └──────────┬───────────┘     │
│             │                            │                  │
│             ▼                            ▼                  │
│  ┌─────────────────────────────────────────────────────┐    │
│  │               依赖模型接入层                          │    │
│  │  ┌─────────────┐  ┌──────────────┐  ┌───────────┐  │    │
│  │  │ Embedding   │  │  Reranker    │  │   LLM    │  │    │
│  │  │ Provider    │  │  Provider    │  │ Provider │  │    │
│  │  └─────────────┘  └──────────────┘  └───────────┘  │    │
│  └─────────────────────────────────────────────────────┘    │
│             │                            │                  │
│             ▼                            ▼                  │
│  ┌─────────────────────────────────────────────────────┐    │
│  │               依赖服务组件层                          │    │
│  │  ┌──────────────┐ ┌──────────────┐ ┌────────────┐  │    │
│  │  │DocumentLoader│ │ TextSplitter │ │DenseStore │  │    │
│  │  └──────────────┘ └──────────────┘ └───────────┘  │    │
│  │                            ┌────────────┐          │    │
│  │                            │SparseStore│          │    │
│  │                            └───────────┘          │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

### 3.3 模型接入层 (Model Access Layer)

**职责**：统一模型调用接口、实例缓存、类型适配

**组件**：
- `model_factory.py` - 工厂函数 + LRU 缓存
- `base.py` - Provider 抽象接口
- `openai_compatible.py` - OpenAI 兼容实现
- `http_client.py` - httpx.AsyncClient 封装

#### 3.3.1 Provider 抽象接口

**位置**：`app/services/providers/base.py`

```python
class LLMProvider(ABC):
    """LLM 提供者抽象接口"""
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass
    
    @abstractmethod
    async def achat(self, messages: list[dict], ...) -> str:
        """异步聊天（非流式）"""
        pass
    
    @abstractmethod
    async def astream(self, messages: list[dict], ...) -> AsyncGenerator[str]:
        """异步聊天（流式）"""
        pass


class EmbeddingProvider(ABC):
    """Embedding 提供者抽象接口"""
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass
    
    @property
    @abstractmethod
    def dimension(self) -> int:
        pass
    
    @abstractmethod
    async def aembed(self, texts: list[str]) -> list[list[float]]:
        """批量嵌入"""
        pass
    
    @abstractmethod
    async def aembed_query(self, query: str) -> list[float]:
        """单查询嵌入"""
        pass


class RerankerProvider(ABC):
    """Reranker 提供者抽象接口"""
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass
    
    @abstractmethod
    async def arerank(
        self,
        query: str,
        documents: list[str],
        top_n: int,
    ) -> list[dict]:
        """重排"""
        pass
```

#### 3.3.2 模型工厂 + LRU 缓存

**位置**：`app/services/providers/model_factory.py`

```python
# 使用 LRU 缓存避免重复创建昂贵的模型实例
llm_cache = LruCache(max_size=20)
embedding_cache = LruCache(max_size=10)
reranker_cache = LruCache(max_size=10)


def create_llm(model: LlmModel) -> LLMProvider:
    """创建或从缓存获取 LLM Provider"""
    cache_key = _llm_cache_key(model)
    
    # 缓存命中
    cached = llm_cache.get(cache_key)
    if cached:
        return cached
    
    # 根据类型创建
    if model.provider == LLMType.OPENAI_COMPATIBLE:
        provider = OpenAICompatibleLLMProvider(
            api_key=decrypt_api_key(model.encrypted_api_key),
            base_url=model.base_url,
            model=model.model_name,
            temperature=model.temperature,
            max_tokens=model.max_tokens,
        )
    # ... 其他类型
    
    # 缓存并返回
    llm_cache.put(cache_key, provider)
    return provider


def create_embedding(model: EmbeddingModel) -> EmbeddingProvider:
    """创建或从缓存获取 Embedding Provider"""
    cache_key = f"{model.id}_{model.user_id}"
    
    cached = embedding_cache.get(cache_key)
    if cached:
        return cached
    
    if model.type == EmbeddingType.OPENAI_COMPATIBLE:
        provider = OpenAICompatibleEmbeddingProvider(
            api_key=decrypt_api_key(model.encrypted_api_key),
            endpoint=model.endpoint,
            model=model.model_name,
            dimension=model.dimension,
            is_dimensionable=model.is_dimensionable,
        )
    
    embedding_cache.put(cache_key, provider)
    return provider


def create_reranker(model: RerankModel) -> RerankerProvider:
    """创建或从缓存获取 Reranker Provider"""
    # ... 类似逻辑
```

#### 3.3.3 HTTP 客户端封装

**位置**：`app/services/providers/http_client.py`

```python
class HttpClient:
    """
    统一 HTTP 客户端
    
    基于 httpx.AsyncClient，提供：
    - Chat Completions
    - Embeddings
    - Rerank
    """
    
    def __init__(self, api_key: str, base_url: str = "", timeout: float = 30.0):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None
    
    async def ensure_client(self) -> httpx.AsyncClient:
        """获取或创建客户端实例"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout),
                headers=self._build_headers(),
            )
        return self._client
    
    async def chat_completions(self, model, messages, stream=False, ...):
        """Chat Completions API"""
        client = await self.ensure_client()
        response = await client.post("/chat/completions", json=payload)
        return response.json()
    
    async def embeddings(self, model, input, dimensions=None, ...):
        """Embeddings API"""
        client = await self.ensure_client()
        response = await client.post("/embeddings", json=payload)
        return [item["embedding"] for item in response.json()["data"]]
    
    async def rerank(self, model, query, documents, top_n, ...):
        """Rerank API (Cohere 兼容格式)"""
        client = await self.ensure_client()
        response = await client.post("/rerank", json=payload)
        return response.json()["results"]
```

**模型接入层依赖关系**：

```
┌─────────────────────────────────────────────────────────────┐
│                      模型接入层                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────┐      ┌─────────────────┐              │
│  │   model_factory  │─────►│  LLMProvider    │              │
│  │   (工厂+LruCache)│      │  (ABC)          │              │
│  └─────────────────┘      └────────┬────────┘              │
│         │                          │                        │
│         │                 ┌────────▼────────┐              │
│         │                 │ OpenAICompat.  │              │
│         │                 │ LLMProvider     │              │
│         │                 └────────┬────────┘              │
│         │                          │                        │
│         │                 ┌────────▼────────┐              │
│         │                 │  HttpClient     │              │
│         │                 │ (httpx.Async)  │              │
│         │                 └─────────────────┘              │
│         │                                                 │
│  ┌──────┴──────────┐      ┌─────────────────┐            │
│  │ EmbeddingProvider│      │ RerankerProvider│            │
│  │  (ABC)          │      │  (ABC)          │            │
│  └─────────────────┘      └─────────────────┘            │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              依赖数据模型层                            │  │
│  │  LlmModel / EmbeddingModel / RerankModel            │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

### 3.4 服务组件层 (Service Components Layer)

**职责**：提供可复用的数据处理和存储抽象组件

#### 3.4.1 DocumentLoader - 文档加载器

**位置**：`app/services/rag/document_loader.py`

**职责**：支持多种文件格式加载

```python
class DocumentLoader:
    """
    文档加载器
    
    支持类型：
    - .txt, .md → TextLoader
    - .pdf → PyPDFLoader
    - .docx → Docx2txtLoader
    - .csv → CSVLoader
    - .json → JSONTextLoader (自定义)
    - .jsonl → JSONLoader
    """
    
    _LOADER_FACTORIES: dict[str, Callable] = {
        ".txt": lambda path, enc: TextLoader(path, encoding=enc),
        ".md": lambda path, enc: TextLoader(path, encoding=enc),
        ".pdf": lambda path, enc: PyPDFLoader(path),
        ".docx": lambda path, enc: Docx2txtLoader(path),
        ".csv": lambda path, enc: CSVLoader(path, encoding=enc),
        ".json": lambda path, enc: JSONTextLoader(path),
        ".jsonl": lambda path, enc: JSONLoader(path, jq_schema=".", json_lines=True),
    }
    
    def load(self, file_path: str | Path, encoding: str = "utf-8") -> list[Document]:
        """加载文件，返回 LangChain Document 列表"""
        ext = path.suffix.lower()
        factory = self._LOADER_FACTORIES.get(ext)
        return factory(str(path), encoding).load()
    
    def load_with_metadata(self, file_path, metadata, encoding="utf-8") -> list[Document]:
        """加载文件并合并元数据"""
        docs = self.load(file_path, encoding)
        for doc in docs:
            doc.metadata.update(metadata)
        return docs
```

#### 3.4.2 TextSplitter - 文本分块器

**位置**：`app/services/rag/text_splitter.py`

**职责**：将长文档分割为可管理的块

```python
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
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.mode = mode
    
    def split_documents(self, documents: list[Document]) -> list[Document]:
        """分割文档列表"""
        splitter = self._get_splitter()
        return splitter.split_documents(documents)
    
    def _get_splitter(self):
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
```

#### 3.4.3 DenseStore - 稠密向量存储抽象

**位置**：`app/services/rag/stores/base.py`

```python
class DenseStore(ABC):
    """稠密向量存储抽象基类"""
    
    @abstractmethod
    async def add_documents(self, docs: list[DocumentUnit]) -> None:
        """添加文档"""
        pass
    
    @abstractmethod
    async def retrieve(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[tuple[DocumentUnit, float]]:
        """检索，返回 (文档, 分数) 列表"""
        pass
    
    @abstractmethod
    async def delete_by_document_ids(self, document_ids: list[str]) -> int:
        """按 document_id 删除"""
        pass
    
    @abstractmethod
    async def delete_by_file_id(self, file_id: str) -> int:
        """按 file_id 删除"""
        pass
```

#### 3.4.4 SparseStore - 稀疏存储抽象

**位置**：`app/services/rag/stores/base.py`

```python
class SparseStore(ABC):
    """稀疏存储抽象基类（BM25 关键词检索）"""
    
    @abstractmethod
    async def add_documents(self, docs: list[DocumentUnit]) -> None:
        """添加文档"""
        pass
    
    @abstractmethod
    async def retrieve(
        self,
        query: str,
        top_k: int = 10,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[tuple[DocumentUnit, float]]:
        """检索，返回 (文档, 分数) 列表"""
        pass
    
    @abstractmethod
    async def delete_by_document_ids(self, document_ids: list[str]) -> int:
        """按 document_id 删除"""
        pass
    
    @abstractmethod
    async def delete_by_file_id(self, file_id: str) -> int:
        """按 file_id 删除"""
        pass
```

**服务组件层依赖关系**：

```
┌─────────────────────────────────────────────────────────────┐
│                     服务组件层                               │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────┐  ┌─────────────────┐                   │
│  │  DocumentLoader │  │  TextSplitter   │                   │
│  │  (文件加载)     │  │  (文本分块)     │                   │
│  └────────┬────────┘  └────────┬────────┘                   │
│           │                    │                            │
│           └─────────┬──────────┘                            │
│                     ▼                                       │
│           ┌─────────────────┐                               │
│           │  DocumentUnit   │◄── RAG模块内流通的核心数据   │
│           └────────┬────────┘                               │
│                    │                                        │
│           ┌────────┴────────┐                               │
│           ▼                 ▼                               │
│  ┌─────────────────┐ ┌─────────────────┐                    │
│  │   DenseStore   │ │  SparseStore   │                    │
│  │    (ABC)       │ │    (ABC)       │                    │
│  └────────┬───────┘ └────────┬───────┘                    │
└───────────┼─────────────────┼───────────────────────────────┘
            │                 │
            ▼                 ▼
    ┌─────────────────┐ ┌─────────────────┐
    │   ChromaDB     │ │  PostgreSQL     │
    │  (稠密向量)     │ │  (FTS+BM25)    │
    └─────────────────┘ └─────────────────┘
```

---

### 3.5 存储层 (Storage Layer)

**职责**：数据持久化，支持多种存储后端

#### 3.5.1 ChromaDenseStore - ChromaDB 实现

**位置**：`app/services/rag/stores/chroma_dense.py`

**特点**：
- 基于 ChromaDB PersistentClient
- 本地持久化存储
- 适合开发和小规模部署

```python
class ChromaDenseStore(DenseStore):
    """
    ChromaDB 稠密向量存储
    
    特点：
    - 本地持久化
    - 自动分批处理
    - 元数据过滤
    """
    
    EMBEDDING_BATCH_SIZE = 100
    
    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        persist_directory: str | Path,
        collection_name: str,
        user_id: int,
    ):
        self.embedding_provider = embedding_provider
        self.persist_directory = Path(persist_directory)
        
        # 创建 ChromaDB 客户端
        self._client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"user_id": str(user_id)},
        )
    
    async def add_documents(self, docs: list[DocumentUnit]) -> None:
        # 批量生成 embedding
        for chunk in self._chunk(docs, batch_size):
            embeddings = await self.embedding_provider.aembed(texts)
            # 异步写入
            await asyncio.to_thread(
                self._collection.add,
                ids=ids, embeddings=embeddings,
                documents=texts, metadatas=metadatas
            )
    
    async def retrieve(self, query_embedding, top_k, metadata_filter=None):
        def _sync_query():
            return self._collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=metadata_filter,
            )
        
        results = await asyncio.to_thread(_sync_query)
        # 转换距离为相似度分数
        return [(DocumentUnit(...), 1.0 - distance) for ...]
```

#### 3.5.2 PGDenseStore - PostgreSQL + pgvector 实现

**位置**：`app/services/rag/stores/pg_dense.py`

**特点**：
- 基于 PostgreSQL + pgvector 扩展
- 支持 SQL 层面的向量运算
- 适合生产环境大规模部署

```python
class PGDenseStore(DenseStore):
    """
    PostgreSQL + pgvector 稠密向量存储
    
    特点：
    - 生产级实现
    - 批量嵌入生成
    - 支持 WHERE 子句过滤
    - 使用子查询确保执行顺序
    """
    
    async def add_documents(self, docs: list[DocumentUnit]) -> None:
        """批量添加文档"""
        session = self.sessionmaker()
        try:
            async with session.begin():
                for chunk in self._chunk_generator(docs, batch_size):
                    # 生成 embeddings
                    embeddings = await self.embedding_provider.aembed(texts)
                    
                    # SQL 批量插入
                    for doc, emb in zip(chunk, embeddings):
                        await session.execute(
                            single_insert_sql,
                            {
                                "embedding": self._vec_to_str(emb),  # 转为 vector 字面量
                                ...
                            }
                        )
        finally:
            await session.close()
    
    async def retrieve(self, query_embedding, top_k, metadata_filter=None):
        """向量检索（使用子查询保证顺序）"""
        base_sql = f"""
        SELECT id, document_id, kb_id, file_id, content, metadata,
            1 - (embedding <=> cast(:embedding as vector)) AS score
        FROM (
            SELECT id, document_id, kb_id, file_id, content, metadata, embedding
            FROM {self.table_name}
            {where_sql}  -- 元数据过滤
        ) AS filtered
        ORDER BY embedding <=> cast(:embedding as vector)
        LIMIT :top_k
        """
        # ... 执行并返回结果
```

#### 3.5.3 PGSparseStore - PostgreSQL + FTS 实现

**位置**：`app/services/rag/stores/pg_sparse.py`

**特点**：
- 基于 PostgreSQL 全文搜索（FTS）
- 使用 jieba 中文分词
- BM25 排序算法

```python
class PGSparseStore(SparseStore):
    """
    PostgreSQL + jieba 稀疏存储（BM25）
    
    特点：
    - jieba 分词（搜索引擎模式）
    - PostgreSQL to_tsquery/to_tsrank
    - 支持元数据过滤
    """
    
    STOPWORDS = {"的", "了", "是", "在"}
    
    def _tokenize(self, text: str) -> str:
        """jieba 分词"""
        tokens = [
            w.strip()
            for w in jieba.lcut_for_search(text)
            if w.strip() and w not in self.STOPWORDS
        ]
        return " ".join(tokens)
    
    async def add_documents(self, docs: list[DocumentUnit]) -> None:
        """添加文档（分词后存储）"""
        for doc in docs:
            tokens = self._tokenize(doc.content)  # jieba 分词
            # 插入到 PostgreSQL
            await session.execute(insert_sql, {
                "tokens": tokens,  # 存储分词结果
                ...
            })
    
    async def retrieve(self, query, top_k, metadata_filter=None):
        """BM25 检索"""
        query_tokens = self._tokenize(query)
        
        sql = f"""
        WITH q AS (
            SELECT plainto_tsquery('simple', :query) AS query
        )
        SELECT id, document_id, kb_id, content, metadata,
               ts_rank(tsv, q.query, 32) AS score
        FROM {self.table_name}, q
        WHERE tsv @@ q.query
        ORDER BY score DESC LIMIT :top_k
        """
        # ... 执行并返回结果
```

**存储层依赖关系**：

```
┌─────────────────────────────────────────────────────────────┐
│                       存储层                                │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────────────────────────────────────────┐  │
│  │                    DenseStore (ABC)                  │  │
│  ├──────────────────────┬──────────────────────────────┤  │
│  │                      │                              │  │
│  ▼                      ▼                              │
│ ┌────────────────┐  ┌────────────────┐                   │
│ │ChromaDenseStore│  │  PGDenseStore  │                   │
│ │                │  │                │                   │
│ │  ChromaDB     │  │  PostgreSQL    │                   │
│ │  本地持久化    │  │  + pgvector   │                   │
│ └────────────────┘  └────────────────┘                   │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐  │
│  │                   SparseStore (ABC)                  │  │
│  └──────────────────────────────┬──────────────────────┘  │
│                                 │                          │
│                                 ▼                          │
│                        ┌────────────────┐                  │
│                        │ PGSparseStore  │                  │
│                        │                │                  │
│                        │  PostgreSQL    │                  │
│                        │  + FTS + jieba │                  │
│                        └────────────────┘                  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. 核心数据流

### 4.1 索引流程

```
用户上传文件
      │
      ▼
┌─────────────────────────────────────────────────────────────────┐
│                    RAGIndexService.index_document()              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. DocumentLoader.load_with_metadata()                          │
│     ┌──────────────────────────────────────────────────────┐   │
│     │  文件路径 → 文件类型检测 → 对应加载器                   │   │
│     │  .pdf → PyPDFLoader                                    │   │
│     │  .docx → Docx2txtLoader                               │   │
│     │  .txt → TextLoader                                    │   │
│     │  ...                                                   │   │
│     └──────────────────────────────────────────────────────┘   │
│                          │                                      │
│                          ▼                                      │
│  2. TextSplitter.split_documents()                             │
│     ┌──────────────────────────────────────────────────────┐   │
│     │  LangChain Document 列表                             │   │
│     │  chunk_size=512, chunk_overlap=50                     │   │
│     │  模式: recursive / markdown                          │   │
│     └──────────────────────────────────────────────────────┘   │
│                          │                                      │
│                          ▼                                      │
│  3. 构建 DocumentUnit 列表                                      │
│     ┌──────────────────────────────────────────────────────┐   │
│     │  document_id: UUID                                  │   │
│     │  kb_id, file_id, user_id                            │   │
│     │  content: chunk 文本                                │   │
│     │  metadata: 原始元数据                                │   │
│     └──────────────────────────────────────────────────────┘   │
│                          │                                      │
│            ┌─────────────┴─────────────┐                       │
│            ▼                           ▼                       │
│  4a. DenseStore.add_documents()  4b. SparseStore.add_documents()│
│     ┌────────────────────┐            ┌────────────────────┐   │
│     │ EmbeddingProvider  │            │ jieba 分词         │   │
│     │ .aembed(texts)    │            │ → tokens          │   │
│     │ ↓                  │            │ ↓                 │   │
│     │ embeddings: list   │            │ to_tsvector       │   │
│     │ ↓                  │            │ ↓                 │   │
│     │ ChromaDB / PG     │            │ PostgreSQL FTS    │   │
│     │ .add()            │            │ .insert()        │   │
│     └────────────────────┘            └────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 检索流程

```
用户查询
      │
      ▼
┌─────────────────────────────────────────────────────────────────┐
│                 RAGRetrievalService.hybrid_retrieve()             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Query Understanding (Multi-Query 扩展)                      │
│     ┌──────────────────────────────────────────────────────┐   │
│     │  n_queries=1: 直接使用原查询                           │   │
│     │  n_queries>1: LLM 改写为多个表达                       │   │
│     │  例如: "如何学习Python" → ["Python学习方法",          │   │
│     │                              "Python入门指南", ...]    │   │
│     └──────────────────────────────────────────────────────┘   │
│                          │                                      │
│  ┌───────────────────────┴───────────────────────────────────┐  │
│  │                    对每个查询执行                          │  │
│  │                                                        │  │
│  │  ┌────────────────────────────────────────────────────┐ │  │
│  │  │ 2a. EmbeddingProvider.aembed_query()              │ │  │
│  │  │     query → query_embedding (list[float])          │ │  │
│  │  └────────────────────────────────────────────────────┘ │  │
│  │                         │                                │  │
│  │         ┌───────────────┴───────────────┐                │  │
│  │         ▼                               ▼                │  │
│  │  ┌────────────────────┐  ┌────────────────────┐       │  │
│  │  │ DenseStore.retrieve │  │ SparseStore.retrieve│       │  │
│  │  │                    │  │                    │       │  │
│  │  │ 向量相似度检索      │  │ BM25 关键词检索     │       │  │
│  │  │ top_k 结果         │  │ top_k 结果         │       │  │
│  │  │ ↓                  │  │ ↓                  │       │  │
│  │  │ (doc, distance)   │  │ (doc, bm25_score) │       │  │
│  │  └────────────────────┘  └────────────────────┘       │  │
│  │                         │                                │  │
│  │                         ▼                                │  │
│  │  ┌────────────────────────────────────────────────────┐ │  │
│  │  │ 3. RRF 融合 (Reciprocal Rank Fusion)             │ │  │
│  │  │                                                  │ │  │
│  │  │ RRF_score(doc) = Σ weight_i × 1/(k + rank_i)   │ │  │
│  │  │                                                  │ │  │
│  │  │ k=60 (默认常数)                                   │ │  │
│  │  │ weight_vector=0.7 (稠密权重)                     │ │  │
│  │  │ weight_sparse=0.3 (稀疏权重)                     │ │  │
│  │  └────────────────────────────────────────────────────┘ │  │
│  │                         │                                │  │
│  └─────────────────────────┼────────────────────────────────┘  │
│                            │                                   │
│                            ▼                                   │
│  4. 去重 + 排序 (按 document_id)                              │
│     ┌──────────────────────────────────────────────────────┐   │
│     │  seen = set()                                       │   │
│     │  for doc, score in all_results:                     │   │
│     │      if doc.document_id not in seen:                │   │
│     │          seen.add(doc.document_id)                  │   │
│     │  return sorted_by_score()[:top_k]                  │   │
│     └──────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 4.3 完整 RAG 流程

```
用户查询
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│  RAGRetrievalService.rag()                                   │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  1. hybrid_retrieve()                                        │
│     ├── Multi-Query 改写                                       │
│     ├── 稠密检索 (向量相似度)                                  │
│     ├── 稀疏检索 (BM25)                                       │
│     ├── RRF 融合                                              │
│     └── 返回 DocumentUnit 列表                                │
│                            │                                  │
│                            ▼                                  │
│  2. RerankerProvider.rerank() (可选)                         │
│     ├── Cross-Encoder 重排                                     │
│     └── 精排 top_n 结果                                       │
│                            │                                  │
│                            ▼                                  │
│  3. build_context()                                          │
│     ├── 合并文档内容                                          │
│     ├── 截断至 max_length                                     │
│     └── 返回上下文字符串                                      │
│                            │                                  │
│                            ▼                                  │
│  4. LLMProvider.achat() (可选)                               │
│     ├── 构造 Prompt (RAG 提示词模板)                          │
│     ├── 加入对话历史 (可选)                                    │
│     └── 返回生成答案                                          │
│                                                               │
│  返回: (answer, documents, sources)                          │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

---

## 5. 核心数据结构

### 5.1 DocumentUnit

**位置**：`app/services/rag/stores/base.py`

**定义**：RAG 模块内流通的核心数据载体

```python
class DocumentUnit(BaseModel):
    """
    RAG 模块内流通的核心数据结构
    
    属性说明：
    - document_id: 外部生成的 UUID，每个 chunk 唯一
    - kb_id: 所属知识库 ID
    - file_id: 所属文件 ID（用于批量删除）
    - content: chunk 文本内容
    - metadata: 扩展元数据（file_name, page_number 等）
    """
    
    document_id: str  # 外部生成的 UUID
    kb_id: str       # 知识库 ID
    file_id: str     # 文件 ID
    content: str     # chunk 文本
    metadata: dict = Field(default_factory=dict)  # 扩展元数据
```

### 5.2 数据流转

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   文件      │────►│  Document  │────►│DocumentUnit │
│  (原始)     │     │(LangChain) │     │             │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                                │
                           ┌────────────────────┤
                           │                    │
                           ▼                    ▼
                   ┌─────────────┐      ┌─────────────┐
                   │ DenseStore  │      │SparseStore  │
                   │             │      │             │
                   │ embedding:  │      │ tokens:     │
                   │ list[float] │      │ str         │
                   └─────────────┘      └─────────────┘
```

---

## 6. 关键设计模式

### 6.1 工厂模式 + LRU 缓存

```python
# model_factory.py
llm_cache = LruCache(max_size=20)

def create_llm(model: LlmModel) -> LLMProvider:
    cache_key = _llm_cache_key(model)
    
    cached = llm_cache.get(cache_key)
    if cached:
        return cached  # 缓存命中，避免重复创建
    
    # 创建新实例
    provider = OpenAICompatibleLLMProvider(...)
    
    llm_cache.put(cache_key, provider)
    return provider
```

**优势**：
- 避免重复创建昂贵的 HTTP 客户端
- 控制内存使用（max_size 限制）
- 线程安全

### 6.2 抽象基类模式

```python
class DenseStore(ABC):
    @abstractmethod
    async def add_documents(self, docs: list[DocumentUnit]) -> None: ...
    
    @abstractmethod
    async def retrieve(self, query_embedding, top_k, ...) -> list[tuple[DocumentUnit, float]]: ...
```

**优势**：
- 定义统一接口
- 支持多种存储后端（ChromaDB, PostgreSQL）
- 便于扩展新存储类型

### 6.3 异步非阻塞 I/O

```python
# ChromaDB 操作是同步的，使用 asyncio.to_thread 包装
async def add_documents(self, docs):
    def _sync_add():
        self._collection.add(ids=ids, embeddings=embeddings, ...)
    
    await asyncio.to_thread(_sync_add)
```

**优势**：
- 不阻塞事件循环
- 支持高并发
- 充分利用异步优势

---

## 7. 组件关系图

### 7.1 完整架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              应用层                                         │
│  ┌─────────────────────────────────────────────────────────────────┐     │
│  │  KnowledgeBaseService                                             │     │
│  │  - CRUD + 权限校验                                                │     │
│  │  - 调用 RAGIndexService / RAGRetrievalService                    │     │
│  └─────────────────────────────────────────────────────────────────┘     │
├─────────────────────────────────────────────────────────────────────────────┤
│                            RAG 服务层                                       │
│  ┌─────────────────────────────┐  ┌─────────────────────────────────┐    │
│  │      RAGIndexService       │  │     RAGRetrievalService         │    │
│  │  ┌───────────────────────┐  │  │  ┌───────────────────────────┐  │    │
│  │  │ DocumentLoader       │  │  │  │  Multi-Query (可选)       │  │    │
│  │  └───────────────────────┘  │  │  └───────────────────────────┘  │    │
│  │  ┌───────────────────────┐  │  │  ┌───────────────────────────┐  │    │
│  │  │ TextSplitter         │  │  │  │  稠密检索 (DenseStore)    │  │    │
│  │  └───────────────────────┘  │  │  └───────────────────────────┘  │    │
│  │                             │  │  ┌───────────────────────────┐  │    │
│  │  ┌───────────────────────┐  │  │  │  稀疏检索 (SparseStore)  │  │    │
│  │  │ EmbeddingProvider     │  │  │  └───────────────────────────┘  │    │
│  │  └───────────────────────┘  │  │  ┌───────────────────────────┐  │    │
│  │  ┌───────────────────────┐  │  │  │  RRF 融合                │  │    │
│  │  │ DenseStore            │  │  │  └───────────────────────────┘  │    │
│  │  └───────────────────────┘  │  │  ┌───────────────────────────┐  │    │
│  │  ┌───────────────────────┐  │  │  │  Reranker (可选)        │  │    │
│  │  │ SparseStore           │  │  │  └───────────────────────────┘  │    │
│  │  └───────────────────────┘  │  │  ┌───────────────────────────┐  │    │
│  └─────────────────────────────┘  │  │  │  LLMProvider (可选)     │  │    │
│                                   │  └─────────────────────────────────┘    │
│                                   └─────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────────────────────────┤
│                            模型接入层                                        │
│  ┌───────────────────────────────────────────────────────────────────┐    │
│  │                      model_factory.py                               │    │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                  │    │
│  │  │ create_llm  │ │create_embed │ │create_rerank│                  │    │
│  │  │   (LRU)     │ │   (LRU)     │ │   (LRU)     │                  │    │
│  │  └─────────────┘ └─────────────┘ └─────────────┘                  │    │
│  └───────────────────────────────────────────────────────────────────┘    │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐        │
│  │LLMProvider  │ │EmbeddingProv│ │RerankerProv │ │ HttpClient  │        │
│  │   (ABC)     │ │   (ABC)     │ │   (ABC)     │ │ (httpx)    │        │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘        │
├─────────────────────────────────────────────────────────────────────────────┤
│                            存储层                                           │
│  ┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────────────┐   │
│  │  ChromaDenseStore  │ │    PGDenseStore     │ │   PGSparseStore     │   │
│  │                     │ │                     │ │                     │   │
│  │     ChromaDB       │ │  PostgreSQL/pgvector│ │  PostgreSQL/FTS     │   │
│  │     (向量)         │ │     (向量)          │ │     (BM25)         │   │
│  └─────────────────────┘ └─────────────────────┘ └─────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 7.2 调用依赖图

```
                    ┌─────────────┐
                    │    Router   │
                    └──────┬──────┘
                           │
                           ▼
                 ┌─────────────────┐
                 │KnowledgeBase    │
                 │   Service       │
                 └────────┬────────┘
                          │
            ┌─────────────┴─────────────┐
            ▼                           ▼
   ┌────────────────┐       ┌─────────────────┐
   │ create_rag_    │       │ create_rag_     │
   │ index_service()│       │ retrieval_svc() │
   └───────┬────────┘       └────────┬────────┘
           │                         │
           ▼                         ▼
   ┌────────────────┐       ┌─────────────────┐
   │ RAGIndexService│       │RAGRetrievalSvc  │
   └───────┬────────┘       └────────┬────────┘
           │                         │
    ┌──────┴──────┐          ┌──────┴──────┐
    ▼             ▼          ▼             ▼
┌────────┐  ┌─────────┐ ┌────────┐  ┌─────────┐
│Document│  │ Text    │ │ Dense  │  │ Sparse  │
│Loader  │  │Splitter │ │Store   │  │ Store   │
└────────┘  └─────────┘ └───┬────┘  └────┬────┘
                            │             │
                            ▼             ▼
                     ┌─────────────────────────┐
                     │     model_factory       │
                     │  (工厂函数 + LRU缓存)   │
                     └───────────┬─────────────┘
                                 │
                    ┌────────────┴────────────┐
                    ▼                         ▼
            ┌────────────┐           ┌────────────┐
            │ Embedding │           │  Reranker  │
            │ Provider  │           │  Provider  │
            └─────┬─────┘           └──────┬─────┘
                  │                         │
                  └───────────┬─────────────┘
                              ▼
                      ┌────────────┐
                      │ HttpClient │
                      │(httpx)    │
                      └────────────┘
```

---

## 8. 关键文件索引

### 8.1 核心文件列表

| 文件路径 | 组件 | 职责 |
|----------|------|------|
| `app/modules/knowledge_base/service.py` | KnowledgeBaseService | 应用层：业务编排 |
| `app/services/rag/retrieval_service.py` | RAGRetrievalService | 混合检索 + RRF + 生成 |
| `app/services/rag/index_service.py` | RAGIndexService | 文档索引管道 |
| `app/services/rag/service_factory.py` | service_factory | RAG 服务工厂 |
| `app/services/rag/stores/base.py` | DenseStore, SparseStore | 存储抽象接口 |
| `app/services/rag/stores/chroma_dense.py` | ChromaDenseStore | ChromaDB 存储 |
| `app/services/rag/stores/pg_dense.py` | PGDenseStore | PG+pgvector 存储 |
| `app/services/rag/stores/pg_sparse.py` | PGSparseStore | PG+FTS+jieba 存储 |
| `app/services/rag/document_loader.py` | DocumentLoader | 多格式文档加载 |
| `app/services/rag/text_splitter.py` | TextSplitter | 文本分块 |
| `app/services/providers/base.py` | Provider ABC | 模型接口定义 |
| `app/services/providers/model_factory.py` | model_factory | 工厂 + LRU 缓存 |
| `app/services/providers/http_client.py` | HttpClient | httpx 封装 |
| `app/services/providers/openai_compatible.py` | OpenAICompatible* | OpenAI 兼容实现 |

### 8.2 数据模型文件

| 文件路径 | 模型 | 说明 |
|----------|------|------|
| `app/modules/knowledge_base/models.py` | KbDocument, KbFile | 知识库 ORM |
| `app/modules/llm_model/models.py` | LlmModel | LLM 配置 |
| `app/modules/embedding_model/models.py` | EmbeddingModel | Embedding 配置 |
| `app/modules/rerank_model/models.py` | RerankModel | Reranker 配置 |

### 8.3 配置相关

| 文件路径 | 说明 |
|----------|------|
| `app/core/settings.py` | Pydantic Settings，包含 RAG 相关配置 |
| `pyproject.toml` | 依赖管理，包含 pgvector, chromadb, jieba 等 |

---

*文档版本：1.0*
*最后更新：2026-04-05*

# AI-Studio-Community 知识库模块架构与工作流

## 一、架构概览

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          API 层 (Router)                                  │
│  POST   /v1/knowledge-bases              - 创建知识库                      │
│  GET    /v1/knowledge-bases              - 列出知识库                     │
│  GET    /v1/knowledge-bases/{kb_id}      - 获取知识库详情                  │
│  PUT    /v1/knowledge-bases/{kb_id}      - 更新知识库                     │
│  DELETE /v1/knowledge-bases/{kb_id}       - 删除知识库                     │
│  POST   /v1/knowledge-bases/{kb_id}/files          - 上传文件             │
│  GET    /v1/knowledge-bases/{kb_id}/files           - 列出文件             │
│  DELETE /v1/knowledge-bases/{kb_id}/files/{fid}     - 删除文件             │
│  POST   /v1/knowledge-bases/{kb_id}/files/{fid}/index - 触发索引           │
│  POST   /v1/knowledge-bases/rag            - RAG 检索/生成                │
│  POST   /v1/knowledge-bases/retrieve       - 纯检索（无 LLM 生成）         │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        服务层 (Business Logic)                           │
│                                                                             │
│  KnowledgeBaseService                                                      │
│  ├── create_kb()      - 生成 collection_name，创建知识库                   │
│  ├── get_kb()        - 获取知识库（带权限校验）                           │
│  ├── list_kbs()       - 分页列表                                          │
│  ├── update_kb()      - 更新知识库字段                                    │
│  ├── delete_kb()      - 从向量库 + MySQL 删除                            │
│  ├── add_file()       - 上传文件，MD5 去重检测                            │
│  ├── get_file()       - 按 ID 获取文件                                   │
│  ├── list_files()     - 分页文件列表                                     │
│  ├── delete_file()    - 从向量库 + MySQL 删除文件                        │
│  ├── index_file()     - 完整索引管道                                     │
│  ├── retrieve()       - 混合检索（稠密向量 + 稀疏 BM25）                   │
│  └── rag()           - 完整 RAG（可选 LLM 生成）                          │
└─────────────────────────────────────────────────────────────────────────┘
          │                                    │                    │
          ▼                                    ▼                    ▼
┌─────────────────────┐  ┌─────────────────────────┐  ┌─────────────────┐
│    Repository 层     │  │      RAG Service        │  │    ChromaDB     │
│                      │  │                         │  │                 │
│  KbDocumentRepository│  │  RAGService             │  │  ChromaVector   │
│  KbFileRepository   │  │  ├── index_document()   │───▶│  Store          │
│  KbChunkRepository  │  │  ├── retrieve()         │  │  ChromaCollec.  │
│                      │  │  └── rag()             │  │                 │
│  (SQLAlchemy ORM)   │  │    (Hybrid Search)     │  └─────────────────┘
└─────────────────────┘  └─────────────────────────┘
          │                          │
          ▼                          ▼
┌─────────────────────┐  ┌─────────────────────────────────┐
│     MySQL 数据库     │  │       模型服务（Factory）          │
│                      │  │                                 │
│  kb_documents       │  │  create_embedding() → Embedding  │
│  kb_files           │  │  create_reranker()  → Reranker  │
│  kb_chunks          │  │  create_llm()       → LLM       │
└─────────────────────┘  └─────────────────────────────────┘
```

---

## 二、核心数据结构

### 2.1 数据库模型

| 模型 | 表名 | 说明 |
|------|------|------|
| `KbDocument` | `kb_documents` | 知识库实体，含 ChromaDB collection 配置 |
| `KbFile` | `kb_files` | 上传文件记录，含处理状态、MD5 去重字段 |
| `KbChunk` | `kb_chunks` | 文件分块记录，内容存 MySQL，向量存 ChromaDB |

**KbDocument 关键字段：**
- `collection_name`: ChromaDB collection 名，格式为 `kb_{user_id}_{name}_{uuid}`
- `embedding_model_id`: 关联 Embedding 模型
- `rerank_model_id`: 关联 Reranker 模型
- `chunk_size` / `chunk_overlap`: 分块配置
- `retrieval_mode`: 检索模式（dense / sparse / hybrid）
- `vector_weight`: 混合检索中向量权重

### 2.2 Schema 响应模型

- `KbDocumentResponse`: 创建/响应知识库
- `KbFileResponse`: 文件信息响应
- `RetrievalRequest` / `RetrievalResponse`: 纯检索请求/响应
- `RAGRequest` / `RAGResponse`: RAG 请求/响应（含 LLM 生成答案）

---

## 三、工作流详解

### 3.1 知识库创建

```
客户端 → POST /knowledge-bases
  → router.create_knowledge_base()
    → service.create_kb()
      → doc_repo.create(user_id, data, collection_name)
        collection_name = f"kb_{user_id}_{data.name.lower()}_{uuid.uuid4().hex[:8]}"
      → 返回 KbDocument（含自动生成的 collection_name）
```

**关键设计：** `collection_name` 在创建时生成，确保每个知识库有独立的 ChromaDB collection。

---

### 3.2 文件上传与索引

```
客户端 → POST /knowledge-bases/{kb_id}/files (multipart/form-data)
  → router.upload_file()
    → 校验文件大小（最大 50MB）
    → 校验文件类型（支持 txt/md/pdf/docx/csv/jsonl）
    → file_storage.save() 保存到本地存储
    → service.add_file()
      → 检查 MD5 去重
      → file_repo.create() 创建 KbFile 记录
    → BackgroundTasks.add_task(index_file_background)
      → service.index_file()
        → service.get_file() 获取文件信息
        → DocumentProcessor.process_file()
          → 根据扩展名调用不同处理器
          → TextSplitter 递归分块（支持重叠）
          → 返回 chunks: [{content, metadata, chunk_index}, ...]
        → rag_service.index_document()
          → embedding_provider.aembed() 将文本转为向量
          → chroma_service.add_texts() 存入 ChromaDB
        → file_repo.update(status="completed", chunk_count=N)
        → chunk_repo.create() 存储每个 chunk 到 MySQL
```

**索引流程图：**

```
文件 (file_path)
    │
    ▼
DocumentProcessor.process_file()
    │
    ├── .txt  → _process_txt()
    ├── .md   → _process_markdown() (按 header 分块)
    ├── .pdf  → _process_pdf() (pdfplumber)
    ├── .docx → _process_docx() (python-docx)
    ├── .csv  → _process_csv()
    └── .jsonl → _process_jsonl()
    │
    ▼
TextSplitter.split_text() 递归分块
    │
    ▼
chunks: List[{content, metadata}]
    │
    ├── content → ChromaDB (向量存储)
    └── metadata {kb_id, file_id, chunk_index} → ChromaDB (metadata)
```

---

### 3.3 纯检索（无 LLM）

```
客户端 → POST /knowledge-bases/retrieve
  → service.retrieve()
    → 获取目标知识库
    → rag_service = get_rag_service(kb)
      → 从 KB 获取 embedding_model_id
      → embedding_repo.get_by_id() 加载 EmbeddingModel
      → create_embedding(model) 获取 EmbeddingProvider
      → 创建 RAGService 实例
    → rag_service.retrieve()
      → 获取 ChromaDB 向量存储
      → 根据 retrieval_mode 选择检索方式：
      │   ├── DENSE:  similarity_search() 纯向量检索
      │   ├── SPARSE: _sparse_search() BM25 关键词检索
      │   └── HYBRID: hybrid_search() RRF 融合两者
      → 如启用 rerank 且配置了 reranker_model：
      │   → reranker_provider.arerank() Cross-Encoder 重排
      → 返回 List[RetrievalResult] (chunk_id, content, score, metadata)
    → 按 score 排序并 limit top_k
    → 返回 RetrievalResponse
```

**混合检索 RRF 融合算法：**

```
RRF_score(doc) = Σ (weight_i × 1/(k + rank_i(doc))) × similarity_i

其中：
- weight_i: DENSE=vector_weight, SPARSE=1-vector_weight
- k: RRF 常数（默认 60）
- rank_i: 各排序列表中的排名
- similarity_i: 1 - cosine_distance
```

---

### 3.4 完整 RAG（带 LLM 生成）

```
客户端 → POST /knowledge-bases/rag (含 llm_model_id)
  → service.rag()
    → 执行与纯检索相同的 retrieval 流程
    → 获取所有结果 (all_results) 和来源 (all_sources)
    → if llm_model_id:
        → llm_repo.get_by_id() 加载 LlmModel
        → create_llm(model) → LLMProvider
        → rag_service.llm_provider = llm_provider
        → rag_service.rag() 完整 RAG
          → retrieve() 重新检索
          → generate():
            → 从 results 构建 context
            → prompt = prompt_template.format(context, question)
            → llm_provider.achat(messages) 调用 LLM
            → 返回生成的答案
        → all_sources = list(set(all_sources + sources))
    → else:
        → answer =拼接检索结果文本
    → 返回 RAGResponse (answer, results, sources, query)
```

---

## 四、依赖注入模式

### 4.1 Router 中的 DI

```python
# app/modules/knowledge_base/router.py

# 1. Repository 工厂函数（接受 DB Session）
def get_kb_document_repository(db: DBAsyncSession) -> KbDocumentRepository:
    return KbDocumentRepository(db)

def get_kb_file_repository(db: DBAsyncSession) -> KbFileRepository:
    return KbFileRepository(db)

# 2. Service 工厂函数（接受 Repository 依赖）
def get_kb_service(
    doc_repo: Annotated[KbDocumentRepository, Depends(get_kb_document_repository)],
    file_repo: Annotated[KbFileRepository, Depends(get_kb_file_repository)],
    chunk_repo: Annotated[KbChunkRepository, Depends(get_kb_chunk_repository)],
) -> KnowledgeBaseService:
    return KnowledgeBaseService(doc_repo, file_repo, chunk_repo)

# 3. 类型别名（简化路由签名）
KBServiceDep = Annotated[KnowledgeBaseService, Depends(get_kb_service)]

# 4. 在路由处理器中使用
@router.post("", response_model=APIResponse[KbDocumentResponse])
async def create_knowledge_base(
    data: KbDocumentCreate,
    current_user: CurrentUser,    # 来自 app.dependencies
    service: KBServiceDep,        # 自动注入
):
    kb = await service.create_kb(current_user.id, data)
    return APIResponse(data=kb)
```

### 4.2 注入链路

```
请求进入
    │
    ▼
DBAsyncSession  ←── Depends(get_db)     # SQLAlchemy 异步会话
    │
    ▼
KbDocumentRepository(db)  ←── Depends(get_kb_document_repository)
KbFileRepository(db)      ←── Depends(get_kb_file_repository)
KbChunkRepository(db)    ←── Depends(get_kb_chunk_repository)
    │
    ▼
KnowledgeBaseService(doc_repo, file_repo, chunk_repo)
    │
    ├── service.doc_repo.db  ← 用于后续 Repository 调用
    ├── service.file_repo.db
    └── service.chunk_repo.db
    │
    ▼
RAGService(embedding_provider, reranker_provider, llm_provider)
    │
    ▼
ChromaVectorStore → ChromaCollection → ChromaDB PersistentClient
```

### 4.3 关键依赖类

| 类型 | 定义位置 | 说明 |
|------|---------|------|
| `CurrentUser` | `app.dependencies` | 当前登录用户（从 JWT 解码） |
| `DBAsyncSession` | `app.dependencies.infras` | SQLAlchemy 异步数据库会话 |
| `KBFileStorage` | `app.dependencies` | 知识库文件存储（本地或云存储） |
| `APIResponse<T>` | `app.common.responses` | 统一响应包装器 |
| `PageData<T>` | `app.common.responses` | 分页数据响应 |

---

## 五、关键设计决策

### 5.1 统一 `/rag` 接口

采用单一接口设计：
- **无 `llm_model_id`**：执行纯语义检索，返回 `RetrievalResponse`
- **有 `llm_model_id`**：执行完整 RAG，调用 LLM 生成答案

**优势：**
- 前端只需一个接口，根据是否有 `llm_model_id` 切换行为
- 减少 API 数量，保持接口简洁

### 5.2 异步后台索引

文件上传立即返回，后台通过 `BackgroundTasks` 执行索引：
- 上传接口返回 `202 Accepted`
- 索引状态通过 `KbFile.status` 字段跟踪

### 5.3 Collection-per-KB

每个知识库有独立的 ChromaDB collection：
- 便于按 KB 删除（直接删除整个 collection）
- 避免不同 KB 的向量混淆
- Collection 名格式：`kb_{user_id}_{name}_{uuid}`

### 5.4 MD5 文件去重

同一知识库内不允许重复上传相同内容的文件：
```python
md5 = hashlib.md5(content).hexdigest()
existing = await file_repo.get_by_md5(kb_id, md5)
if existing:
    raise ValidationException("文件已存在")
```

### 5.5 混合检索 + RRF 融合

结合稠密向量检索（语义相似性）和稀疏 BM25 检索（关键词匹配）：

```python
if retrieval_mode == "hybrid":
    results = chroma_service.hybrid_search(
        query=query,
        vector_weight=vector_weight,  # 默认 0.7
    )
```

---

## 六、API 路由汇总

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/v1/knowledge-bases` | 创建知识库 |
| GET | `/v1/knowledge-bases` | 列出知识库（分页） |
| GET | `/v1/knowledge-bases/{kb_id}` | 获取知识库详情 |
| PUT | `/v1/knowledge-bases/{kb_id}` | 更新知识库配置 |
| DELETE | `/v1/knowledge-bases/{kb_id}` | 删除知识库（级联删除） |
| POST | `/v1/knowledge-bases/{kb_id}/files` | 上传文件 |
| GET | `/v1/knowledge-bases/{kb_id}/files` | 列出文件（分页） |
| GET | `/v1/knowledge-bases/{kb_id}/files/{file_id}` | 获取文件详情 |
| DELETE | `/v1/knowledge-bases/{kb_id}/files/{file_id}` | 删除文件 |
| POST | `/v1/knowledge-bases/{kb_id}/files/{file_id}/index` | 触发重新索引 |
| POST | `/v1/knowledge-bases/rag` | RAG 检索/生成 |
| POST | `/v1/knowledge-bases/retrieve` | 纯检索 |

---

## 七、文件结构

```
app/modules/knowledge_base/
├── __init__.py          # 模块导出
├── models.py            # SQLAlchemy 模型（KbDocument, KbFile, KbChunk）
├── schema.py            # Pydantic Schema（请求/响应）
├── repository.py         # 数据访问层
│   ├── KbDocumentRepository
│   ├── KbFileRepository
│   └── KbChunkRepository
├── service.py           # 业务逻辑层
├── service_factory.py   # RAGService 工厂
└── router.py            # API 路由定义

app/services/
├── rag/
│   ├── rag_service.py   # RAG 核心服务
│   └── text_splitter.py # 文档分块工具
├── vectordb/
│   └── chroma_service.py # ChromaDB 封装
└── factory/
    └── model_factory.py  # LLM/Embedding/Reranker 工厂

app/common/
├── responses.py          # APIResponse, PageData
├── exceptions.py         # 自定义异常
├── storage.py            # KnowledgeFileStorage
└── base.py              # SQLAlchemy Base
```

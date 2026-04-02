from abc import ABC
from typing import Any

from pydantic import BaseModel

# ============================================================================
# Basic flow data paradigm DocumentUnit
# ============================================================================


class DocumentUnit(BaseModel):
    """
    RAG module/service
    circlulating data structure for indexing and retrieval
    """

    pass


# ============================================================================
# RAGIndexService
# ============================================================================


class DenseStore(ABC):
    """
    Dense Store for
    - vector storage
    - dense retrieval with metafilter
    """

    def add_documents(self, docs: list[DocumentUnit]):
        """Add documents to the dense store"""
        pass

    def retrieve(
        self, query: str, top_k: int = 10, metadata_filter: dict[str, Any] = None
    ) -> list[DocumentUnit]:
        """
        Retrieve documents or embeddings matching the query
        """
        pass


class SparseStore(ABC):
    """
    Sparse Store for sparse storage for
    - content storeage
    - BM25 key-words search with meatafilter
    """

    def add_documents(self, docs: list[DocumentUnit]):
        """Add documents to the dense store"""
        pass

    def retrieve(
        self, query: str, top_k: int = 10, metadata_filter: dict[str, Any] = None
    ) -> list[DocumentUnit]:
        """
        Retrieve documents or embeddings matching the query
        """
        pass


class DocumentLoader:
    """
    Document Loader for loading documents from different

    core function logic:
    - accept
        -file_path: Union[str, Path],
        - encoding: Optional[str] = "utf-8",
    - use
        - langchain.document_loaders to load documents
        - Use the registry and factory design model to cover common types of files as much as possible
    - return list[langchain_core.documents.Document]

    """

    pass


class TextSplitter:
    """
    Text Splitter for splitting documents into chunks

    core function logic:
    - accept list[langchain_core.documents.Document]
    - use laanghcin_splitters to split documents
    - return list[DocumnetUnit]
    """

    pass


class RAGIndexService:
    """
    RAG Index Service for document indexing.

    This service handles Document indexing:
    - file → chunks → embeddings → vector store
                    → sparse strore
    This service denpends on :
    - embedding_provider:EmbeddingProvider
    - dense_store:DenseStore
    - sparse_store:SparseStore
    - document_loader:DocumentLoader
    - text_splitter:TextSplitter
    """

    def __init__(
        self,
        vector_store: DenseStore,
        sparse_store: SparseStore,
        embedding_provider: EmbeddingProvider,
    ) -> None:
        self.vector_store = vector_store
        self.sparse_store = sparse_store
        self.embedding_provider = embedding_provider

        self.document_loader: DocumentLoader = DocumentLoader()
        self.text_splitter: TextSplitter = TextSplitter()
        pass

    def index_document(self) -> None:
        """Index a document"""
        pass

    # 其他函数


# ============================================================================
# RAGRretrievalService
# ============================================================================


class RAGRretrievalService:
    """
    1)RAG Service for retrieval and generation.
    2)完整检索流程:
        1. 接收用户查询
        2. Query Understanding（意图识别 / 改写 / 扩展）
        3. Multi Query 生成（q1, q2, q3）
        4. 多路检索：
        - Vector Search（语义）
        - BM25 Search（关键词）
        - Metadata Filter（过滤）
        5. RRF 融合结果
        6. Reranker 精排（Cross Encoder）
        7. Context 构建（合并 / 去重 / 压缩）
        8. LLM 生成答案
        9. 返回结果
    3)This service handles:
    - Hybrid retrieval (dense + sparse with RRF fusion)
    - Optional reranking (Cross-Encoder)
    - Optional LLM generation (answer synthesis)
    """

    def __init__(
        self,
        vector_store: DenseStore,
        sparse_store: SparseStore,
        embedding_provider: EmbeddingProvider,
        reanker_provider: RerankerProvider | None = None,
        llm_provider: LLMProvider | None = None,
    ) -> None:
        self.vector_store = vector_store
        self.sparse_store = sparse_store
        self.embedding_provider = embedding_provider
        self.reanker_provider = reanker_provider
        self.llm_provider = llm_provider

    def rewrite_query(self, query: str) -> list[str]:
        """
        Query Understanding Service
        use:
        - self.llm_provider
        - prompting engineering/peompt templete
        args:
            :query
        returns queries
        """
        pass

    def hybrid_search(self) -> list[DocumentUnit]:
        pass

    def build_context(self, documents: list[DocumentUnit]) -> str:

        pass

    def rrf_fusion(self):
        pass

    default_prompt = """
            你是一个问答助手。请根据以下参考资料回答用户的问题。
            参考资料:{context}
            用户问题: {question}
            请基于参考资料给出准确、详细的回答。如果参考资料中没有相关信息，请说明无法回答。
        """

    def generate(
        self,
        query: str,
        retrieval_results: list[DocumentUnit],
        prompt_template: str = default_prompt,
    ) -> str:

        return ""

    def rag():
        pass

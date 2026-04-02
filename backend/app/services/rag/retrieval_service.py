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

    async def _expand_query(self, query: str, n: int = 1) -> list[str]:
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

        response = await self.llm_provider.achat([
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
        queries = await self._expand_query(query, n=n_queries)

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
        metadata_filter: dict[str, Any] | None = None,
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
                [f"{doc.content[:200]}..." for doc in documents]
            )

        return answer, documents, sources
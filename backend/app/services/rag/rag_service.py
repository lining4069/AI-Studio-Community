"""
RAG Service - Retrieval Augmented Generation pipeline.

Orchestrates the full RAG workflow:
1. Query Understanding (optional query expansion)
2. Multi-Query Generation (optional)
3. Hybrid Search (dense vector + sparse/BM25)
4. RRF Fusion
5. Reranking (optional)
6. LLM Generation (optional)
"""

import uuid

from loguru import logger

from app.modules.knowledge_base.models import RetrievalMode
from app.modules.knowledge_base.schema import RetrievalResult
from app.services.providers.base import EmbeddingProvider, LLMProvider, RerankerProvider
from app.services.rag.text_splitter import DocumentProcessor, TextSplitter
from app.services.vectordb.base import VectorDBProvider, VectorStore


class RAGService:
    """
    RAG Service for retrieval and generation.

    This service handles:
    - Document indexing (file → chunks → embeddings → vector store)
    - Hybrid retrieval (dense + sparse with RRF fusion)
    - Optional reranking (Cross-Encoder)
    - Optional LLM generation (answer synthesis)
    """

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        reranker_provider: RerankerProvider | None = None,
        llm_provider: LLMProvider | None = None,
        vector_provider: VectorDBProvider | None = None,
    ):
        """
        Initialize RAG Service.

        Args:
            embedding_provider: Provider for text embeddings
            reranker_provider: Optional provider for reranking
            llm_provider: Optional provider for LLM generation
            vector_provider: VectorDB provider (ChromaDB, Milvus, etc.)
        """
        self.embedding_provider = embedding_provider
        self.reranker_provider = reranker_provider
        self.llm_provider = llm_provider
        self.vector_provider = vector_provider
        self._text_splitter = TextSplitter()
        self._doc_processor = DocumentProcessor()

    def get_vector_store(
        self,
        collection_name: str,
        user_id: int,
    ) -> VectorStore:
        """
        Get a vector store for a collection.

        Args:
            collection_name: Name of the collection (typically kb_id)
            user_id: User ID for data isolation

        Returns:
            VectorStore instance
        """
        if self.vector_provider is None:
            raise ValueError("vector_provider is required")
        return self.vector_provider.get_vector_store(collection_name, user_id)

    # =========================================================================
    # Document Indexing
    # =========================================================================

    async def index_document(
        self,
        kb_id: str,
        file_id: str,
        file_path: str,
        file_name: str,
        user_id: int,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        collection_name: str | None = None,
        metadata: dict | None = None,
    ) -> tuple[int, list[str]]:
        """
        Index a document into the vector store.

        Args:
            kb_id: Knowledge base ID
            file_id: File ID in database
            file_path: Path to the file
            file_name: Original file name
            user_id: User ID for data isolation
            chunk_size: Chunk size for splitting
            chunk_overlap: Overlap between chunks
            collection_name: Collection name (defaults to kb_id)
            metadata: Additional metadata for chunks

        Returns:
            Tuple of (chunk_count, chunk_ids)
        """
        collection_name = collection_name or kb_id
        vector_store = self.get_vector_store(collection_name, user_id)

        # Process document into chunks
        processor = DocumentProcessor(
            splitter=TextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        )

        doc_metadata = {
            "kb_id": kb_id,
            "file_id": file_id,
            "file_name": file_name,
            **(metadata or {}),
        }

        chunks = await processor.process_file(file_path, doc_metadata)

        if not chunks:
            logger.warning(f"No chunks generated from file: {file_path}")
            return 0, []

        # Prepare texts and metadata
        texts = [c["content"] for c in chunks]
        chunk_metadatas = [c["metadata"] for c in chunks]
        chunk_ids = [str(uuid.uuid4()) for _ in chunks]

        # Compute embeddings
        embeddings = await self.embedding_provider.aembed(texts)

        # Add to vector store
        vector_store.add_texts(
            texts=texts,
            embeddings=embeddings,
            metadatas=chunk_metadatas,
            ids=chunk_ids,
        )

        logger.info(
            f"Indexed {len(chunks)} chunks from {file_name} into collection {collection_name}"
        )

        return len(chunks), chunk_ids

    async def delete_document(
        self,
        file_id: str,
        collection_name: str,
        user_id: int,
    ) -> int:
        """
        Delete a document from the vector store.

        Args:
            file_id: File ID to delete
            collection_name: Collection name
            user_id: User ID for data isolation

        Returns:
            Number of chunks deleted
        """
        vector_store = self.get_vector_store(collection_name, user_id)
        deleted = vector_store.delete_by_file_id(file_id)
        logger.info(f"Deleted {deleted} chunks for file {file_id}")
        return deleted

    async def delete_knowledge_base(
        self,
        collection_name: str,
        user_id: int,
    ) -> int:
        """
        Delete all chunks for a knowledge base.

        Args:
            collection_name: Collection name
            user_id: User ID for data isolation

        Returns:
            Number of chunks deleted
        """
        vector_store = self.get_vector_store(collection_name, user_id)
        count_before = vector_store.count()
        vector_store.delete_collection()
        logger.info(f"Deleted all chunks for KB {collection_name}")
        return count_before

    # =========================================================================
    # Retrieval Pipeline
    # =========================================================================

    async def retrieve(
        self,
        query: str,
        collection_name: str,
        user_id: int,
        top_k: int = 5,
        retrieval_mode: RetrievalMode = RetrievalMode.HYBRID,
        vector_weight: float = 0.7,
        similarity_threshold: float = 0.0,
        enable_rerank: bool = False,
        rerank_top_k: int = 3,
        filter_metadata: dict | None = None,
    ) -> list[RetrievalResult]:
        """
        Retrieve relevant chunks for a query.

        Args:
            query: Query text
            collection_name: Collection name
            user_id: User ID for data isolation
            top_k: Number of initial results
            retrieval_mode: dense, sparse, or hybrid
            vector_weight: Weight for dense results in hybrid mode
            similarity_threshold: Minimum similarity threshold
            enable_rerank: Whether to use reranking
            rerank_top_k: Number of results after reranking
            filter_metadata: Optional metadata filters

        Returns:
            List of RetrievalResult objects
        """
        vector_store = self.get_vector_store(collection_name, user_id)

        # Perform search based on mode
        if retrieval_mode == RetrievalMode.DENSE:
            raw_results = vector_store.similarity_search(
                query=query,
                k=top_k,
                filter_metadata=filter_metadata,
            )
        elif retrieval_mode == RetrievalMode.SPARSE:
            # Sparse search through ChromaDB
            raw_results = self._sparse_search(
                vector_store, query, top_k, filter_metadata
            )
        else:  # HYBRID
            raw_results = vector_store.hybrid_search(
                query=query,
                k=top_k,
                vector_weight=vector_weight,
                filter_metadata=filter_metadata,
            )

        # Filter by threshold
        results = [
            RetrievalResult(
                chunk_id=chunk_id,
                content=text,
                score=score,
                metadata={},
            )
            for chunk_id, text, score in raw_results
            if score >= similarity_threshold
        ]

        # Reranking if enabled
        if enable_rerank and self.reranker_provider and len(results) > 1:
            results = await self._rerank(
                query=query,
                results=results,
                top_k=rerank_top_k,
            )

        return results

    def _sparse_search(
        self,
        vector_store: VectorStore,
        query: str,
        k: int,
        filter_metadata: dict | None,
    ) -> list[tuple[str, str, float]]:
        """Perform sparse/BM25 search"""
        # NOTE: sparse search is chromadb-specific; other backends fall back to dense
        try:
            return vector_store.collection.query_sparse(
                query_texts=[query],
                n_results=k,
                where_filter=filter_metadata,
            )
        except Exception as e:
            logger.warning(f"Sparse search not supported, falling back to dense: {e}")
            return vector_store.similarity_search(query, k, filter_metadata)

    async def _rerank(
        self,
        query: str,
        results: list[RetrievalResult],
        top_k: int,
    ) -> list[RetrievalResult]:
        """Rerank results using cross-encoder"""
        if not self.reranker_provider:
            return results[:top_k]

        try:
            documents = [r.content for r in results]
            reranked = await self.reranker_provider.arerank(
                query=query,
                documents=documents,
                top_n=top_k,
            )

            # Map back to results
            reranked_results = []

            for item in reranked:
                doc_text = item.get("document", "")
                # Find original result by content match
                for r in results:
                    if r.content == doc_text:
                        r.score = item.get("score", r.score)
                        reranked_results.append(r)
                        break

            return reranked_results[:top_k]
        except Exception as e:
            logger.warning(f"Reranking failed: {e}")
            return results[:top_k]

    # =========================================================================
    # LLM Generation
    # =========================================================================

    async def generate(
        self,
        query: str,
        retrieval_results: list[RetrievalResult],
        prompt_template: str | None = None,
        conversation_history: list[dict] | None = None,
    ) -> str:
        """
        Generate answer from retrieved context.

        Args:
            query: User query
            retrieval_results: Retrieved context chunks
            prompt_template: Custom prompt template
            conversation_history: Previous conversation turns

        Returns:
            Generated answer string
        """
        if not self.llm_provider:
            raise ValueError("LLM provider not configured")

        if not retrieval_results:
            return "I couldn't find any relevant information to answer your question."

        # Build context from results
        context_parts = []
        for i, result in enumerate(retrieval_results, 1):
            source_info = ""
            if result.metadata.get("file_name"):
                source_info = f" [{result.metadata['file_name']}]"
            context_parts.append(f"[{i}]{source_info}\n{result.content}")

        context = "\n\n".join(context_parts)

        # Build prompt
        if prompt_template:
            prompt = prompt_template.format(context=context, question=query)
        else:
            prompt = self._default_prompt.format(context=context, question=query)

        # Add conversation history if provided
        messages = []
        if conversation_history:
            for turn in conversation_history[-3:]:  # Last 3 turns
                messages.append({"role": "user", "content": turn.get("question", "")})
                messages.append(
                    {"role": "assistant", "content": turn.get("answer", "")}
                )

        messages.append({"role": "user", "content": prompt})

        # Generate
        response = await self.llm_provider.achat(messages)
        return response

    _default_prompt = """
        你是一个问答助手。请根据以下参考资料回答用户的问题。
        参考资料:{context}
        用户问题: {question}
        请基于参考资料给出准确、详细的回答。如果参考资料中没有相关信息，请说明无法回答。
    """

    # =========================================================================
    # Full RAG Pipeline
    # =========================================================================

    async def rag(
        self,
        query: str,
        collection_name: str,
        user_id: int,
        top_k: int = 5,
        retrieval_mode: RetrievalMode = RetrievalMode.HYBRID,
        vector_weight: float = 0.7,
        similarity_threshold: float = 0.0,
        enable_rerank: bool = True,
        rerank_top_k: int = 3,
        filter_metadata: dict | None = None,
        prompt_template: str | None = None,
        conversation_history: list[dict] | None = None,
    ) -> tuple[str, list[RetrievalResult], list[str]]:
        """
        Full RAG pipeline: retrieve + generate.

        Args:
            query: User query
            collection_name: Collection name
            user_id: User ID for data isolation
            top_k: Number of retrieval results
            retrieval_mode: dense, sparse, or hybrid
            vector_weight: Weight for dense in hybrid mode
            similarity_threshold: Minimum similarity threshold
            enable_rerank: Whether to use reranking
            rerank_top_k: Number of results after reranking
            filter_metadata: Metadata filters
            prompt_template: Custom prompt template
            conversation_history: Conversation history

        Returns:
            Tuple of (generated_answer, retrieval_results, sources)
        """
        # Retrieval
        results = await self.retrieve(
            query=query,
            collection_name=collection_name,
            user_id=user_id,
            top_k=top_k,
            retrieval_mode=retrieval_mode,
            vector_weight=vector_weight,
            similarity_threshold=similarity_threshold,
            enable_rerank=enable_rerank,
            rerank_top_k=rerank_top_k,
            filter_metadata=filter_metadata,
        )

        # Generation
        if self.llm_provider:
            answer = await self.generate(
                query=query,
                retrieval_results=results,
                prompt_template=prompt_template,
                conversation_history=conversation_history,
            )
        else:
            # No LLM configured, just return retrieved content
            answer = "\n\n".join(
                [f"[Score: {r.score:.3f}] {r.content[:200]}..." for r in results]
            )

        # Extract sources
        sources = list(
            {
                r.metadata.get("file_name", "Unknown")
                for r in results
                if r.metadata.get("file_name")
            }
        )

        return answer, results, sources

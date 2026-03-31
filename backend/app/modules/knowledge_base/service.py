"""
Knowledge Base service for business logic.
"""

import hashlib
import uuid

from loguru import logger

from app.common.exceptions import NotFoundException, ValidationException
from app.core.settings import BASE_DIR
from app.modules.knowledge_base.models import KbChunk, KbDocument, KbFile, RetrievalMode
from app.modules.knowledge_base.repository import (
    KbChunkRepository,
    KbDocumentRepository,
    KbFileRepository,
)
from app.modules.knowledge_base.schema import (
    KbDocumentCreate,
    KbDocumentUpdate,
    RAGRequest,
    RAGResponse,
    RetrievalConfig,
    RetrievalRequest,
    RetrievalResponse,
)
from app.services.rag.service_factory import get_rag_service


class KnowledgeBaseService:
    """Business logic for Knowledge Base"""

    def __init__(
        self,
        doc_repo: KbDocumentRepository,
        file_repo: KbFileRepository,
        chunk_repo: KbChunkRepository,
    ):
        self.doc_repo = doc_repo
        self.file_repo = file_repo
        self.chunk_repo = chunk_repo

    # =========================================================================
    # Document (Knowledge Base) CRUD
    # =========================================================================

    async def create_kb(self, user_id: int, data: KbDocumentCreate) -> KbDocument:
        """Create a new Knowledge Base"""
        # Check name uniqueness
        existing = await self.doc_repo.get_by_name(user_id, data.name)
        if existing:
            raise ValidationException(
                f"Knowledge base with name '{data.name}' already exists"
            )

        # Generate collection name
        collection_name = (
            f"kb_{user_id}_{data.name.lower().replace(' ', '_')}_{uuid.uuid4().hex[:8]}"
        )

        # Create document with collection_name
        kb = await self.doc_repo.create(user_id, data, collection_name=collection_name)

        return kb

    async def get_kb(self, kb_id: str, user_id: int) -> KbDocument:
        """Get a Knowledge Base by ID"""
        kb = await self.doc_repo.get_by_id(kb_id, user_id)
        if not kb:
            raise NotFoundException("Knowledge Base", kb_id)
        return kb

    async def list_kbs(
        self, user_id: int, page: int = 1, page_size: int = 20
    ) -> tuple[list[KbDocument], int]:
        """List Knowledge Bases"""
        return await self.doc_repo.list_by_user(user_id, page, page_size)

    async def update_kb(
        self, kb_id: str, user_id: int, data: KbDocumentUpdate
    ) -> KbDocument:
        """Update a Knowledge Base"""
        kb = await self.get_kb(kb_id, user_id)

        # Check name uniqueness if name is being changed
        if data.name and data.name != kb.name:
            existing = await self.doc_repo.get_by_name(user_id, data.name)
            if existing:
                raise ValidationException(
                    f"Knowledge base with name '{data.name}' already exists"
                )

        updated = await self.doc_repo.update(kb, data)
        return updated

    async def delete_kb(self, kb_id: str, user_id: int) -> None:
        """Delete a Knowledge Base and all its data"""
        kb = await self.get_kb(kb_id, user_id)

        # Delete from vector store
        try:
            rag_service = await get_rag_service(kb)
            await rag_service.delete_knowledge_base(kb.collection_name, kb.user_id)
        except Exception as e:
            logger.error(f"Failed to delete vector store: {e}")

        # Delete chunks from DB
        await self.chunk_repo.delete_by_kb(kb_id)

        # Delete files from DB (chunks should cascade)
        # Note: actual file deletion from storage should be handled by a background task

        # Delete KB
        await self.doc_repo.delete(kb)

    # =========================================================================
    # File Operations
    # =========================================================================

    async def add_file(
        self,
        user_id: int,
        kb_id: str,
        file_name: str,
        file_path: str,
        file_size: int,
        file_type: str,
        content: bytes,
    ) -> KbFile:
        """
        Add a file to a Knowledge Base.

        Args:
            user_id: User ID
            kb_id: Knowledge Base ID
            file_name: Original file name
            file_path: Stored file path
            file_size: File size in bytes
            file_type: MIME type
            content: File content bytes

        Returns:
            Created KbFile
        """
        # Validate KB exists
        await self.get_kb(kb_id, user_id)

        # Calculate MD5 for deduplication
        md5 = hashlib.md5(content).hexdigest()

        # Check for duplicate
        existing = await self.file_repo.get_by_md5(kb_id, md5)
        if existing:
            raise ValidationException(
                f"File '{file_name}' has already been uploaded to this knowledge base"
            )

        # Create file record with MD5
        file_data = type(
            "obj",
            (object,),
            {
                "file_name": file_name,
                "file_path": file_path,
                "file_size": file_size,
                "file_type": file_type,
            },
        )()

        kb_file = await self.file_repo.create(user_id, kb_id, file_data, file_md5=md5)

        return kb_file

    async def get_file(self, file_id: str, user_id: int) -> KbFile:
        """Get a file by ID"""
        file = await self.file_repo.get_by_id(file_id, user_id)
        if not file:
            raise NotFoundException("File", file_id)
        return file

    async def list_files(
        self,
        kb_id: str,
        user_id: int,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
    ) -> tuple[list[KbFile], int]:
        """List files in a Knowledge Base"""
        # Verify KB exists
        await self.get_kb(kb_id, user_id)
        return await self.file_repo.list_by_kb(kb_id, user_id, page, page_size, status)

    async def delete_file(self, file_id: str, user_id: int) -> None:
        """Delete a file and its chunks"""
        file = await self.get_file(file_id, user_id)
        kb = await self.get_kb(file.kb_id, user_id)

        # Delete from vector store
        try:
            rag_service = await get_rag_service(kb)
            await rag_service.delete_document(file_id, kb.collection_name, kb.user_id)
        except Exception as e:
            logger.error(f"Failed to delete from vector store: {e}")

        # Delete chunks from DB
        await self.chunk_repo.delete_by_file(file_id)

        # Delete file record
        await self.file_repo.delete(file)

    # =========================================================================
    # Chunk Operations
    # =========================================================================

    async def list_chunks(
        self,
        file_id: str,
        user_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[KbChunk], int]:
        """List chunks in a file"""
        # Verify file exists
        await self.get_file(file_id, user_id)
        return await self.chunk_repo.list_by_file(file_id, user_id, page, page_size)

    # =========================================================================
    # Indexing Pipeline
    # =========================================================================

    async def index_file(
        self,
        file_id: str,
        user_id: int,
    ) -> int:
        """
        Index a file into the vector store.

        Args:
            file_id: File ID
            user_id: User ID

        Returns:
            Number of chunks indexed
        """
        file = await self.get_file(file_id, user_id)
        kb = await self.get_kb(file.kb_id, user_id)

        # Resolve relative file path to absolute path
        # file.file_path is stored as /storage/knowledge/... (relative to BASE_DIR)
        absolute_file_path = str(BASE_DIR / file.file_path.lstrip("/"))

        # Get or create RAG service
        rag_service = await get_rag_service(kb)

        try:
            # Index document
            chunk_count, chunk_ids = await rag_service.index_document(
                kb_id=kb.id,
                file_id=file_id,
                file_path=absolute_file_path,
                file_name=file.file_name,
                user_id=kb.user_id,
                chunk_size=kb.chunk_size,
                chunk_overlap=kb.chunk_overlap,
                collection_name=kb.collection_name,
                metadata={"kb_id": kb.id, "file_id": file_id},
            )

            # Update file status
            await self.file_repo.update(
                file, status="completed", chunk_count=chunk_count
            )

            # Store chunk records in DB
            for i, chunk_id in enumerate(chunk_ids):
                await self.chunk_repo.create(
                    user_id=user_id,
                    kb_id=kb.id,
                    file_id=file_id,
                    content=f"[chunk {chunk_id}]",  # Content stored in vector DB
                    chunk_index=i,
                    metadata={"chunk_id": chunk_id, "vector_id": chunk_id},
                )

            return chunk_count

        except Exception as e:
            logger.error(f"Failed to index file {file_id}: {e}")
            await self.file_repo.update(file, status="failed", failed_reason=str(e))
            raise

    # =========================================================================
    # Retrieval & RAG
    # =========================================================================

    async def retrieve(
        self,
        user_id: int,
        request: RetrievalRequest,
    ) -> RetrievalResponse:
        """
        Retrieve relevant chunks for a query.

        Args:
            user_id: User ID
            request: Retrieval request

        Returns:
            RetrievalResponse with results
        """
        # Get KBs to search
        if not request.kb_ids:
            raise ValidationException("kb_ids is required")

        kb_id = request.kb_ids[0]

        # Validate primary KB exists
        await self.get_kb(kb_id, user_id)

        # Determine config
        config = request.config or RetrievalConfig()
        if request.config is None:
            # Use KB defaults
            search_kb = await self.get_kb(kb_id, user_id)
            config.retrieval_mode = RetrievalMode(search_kb.retrieval_mode)
            config.top_k = search_kb.top_k
            config.similarity_threshold = search_kb.similarity_threshold
            config.vector_weight = search_kb.vector_weight
            config.enable_rerank = search_kb.enable_rerank
            config.rerank_top_k = search_kb.rerank_top_k

        # All KBs to search
        search_kb_ids = request.kb_ids
        all_results = []

        for search_kb_id in search_kb_ids:
            search_kb = await self.get_kb(search_kb_id, user_id)
            search_rag_service = await get_rag_service(search_kb)

            # Retrieve
            results = await search_rag_service.retrieve(
                query=request.query,
                collection_name=search_kb.collection_name,
                user_id=search_kb.user_id,
                top_k=config.top_k,
                retrieval_mode=config.retrieval_mode,
                vector_weight=config.vector_weight,
                similarity_threshold=config.similarity_threshold,
                enable_rerank=config.enable_rerank and search_kb.enable_rerank,
                rerank_top_k=config.rerank_top_k,
            )

            all_results.extend(results)

        # Sort by score and limit
        all_results.sort(key=lambda x: x.score, reverse=True)
        all_results = all_results[: config.top_k]

        return RetrievalResponse(
            results=all_results,
            query=request.query,
            total=len(all_results),
        )

    async def rag(
        self,
        user_id: int,
        request: RAGRequest,
    ) -> RAGResponse:
        """
        Full RAG pipeline: retrieve + generate.

        Args:
            user_id: User ID
            request: RAG request

        Returns:
            RAGResponse with answer and sources
        """
        # Get KBs to search
        if not request.kb_ids:
            raise ValidationException("kb_ids is required")

        kb_id = request.kb_ids[0]

        kb = await self.get_kb(kb_id, user_id)

        # Get LLM provider if LLM model ID provided
        llm_provider = None
        if request.llm_model_id:
            from app.modules.llm_model.repository import LlmModelRepository
            from app.services.providers.model_factory import create_llm

            llm_repo = LlmModelRepository(self.doc_repo.db)
            llm_model = await llm_repo.get_by_id(request.llm_model_id, user_id)
            if not llm_model:
                raise NotFoundException("LLMModel", request.llm_model_id)
            llm_provider = create_llm(llm_model)

        # Get or create RAG service
        rag_service = await get_rag_service(kb, llm_provider=llm_provider)

        # Determine config
        config = request.config or RetrievalConfig()
        if request.config is None:
            # Use KB defaults
            config.retrieval_mode = RetrievalMode(kb.retrieval_mode)
            config.top_k = kb.top_k
            config.similarity_threshold = kb.similarity_threshold
            config.vector_weight = kb.vector_weight
            config.enable_rerank = kb.enable_rerank
            config.rerank_top_k = kb.rerank_top_k

        # Determine KBs to search
        search_kb_ids = request.kb_ids
        all_results = []
        all_sources = []

        for search_kb_id in search_kb_ids:
            search_kb = await self.get_kb(search_kb_id, user_id)
            search_rag_service = await get_rag_service(search_kb)

            # Retrieve
            results = await search_rag_service.retrieve(
                query=request.query,
                collection_name=search_kb.collection_name,
                user_id=search_kb.user_id,
                top_k=config.top_k,
                retrieval_mode=config.retrieval_mode,
                vector_weight=config.vector_weight,
                similarity_threshold=config.similarity_threshold,
                enable_rerank=config.enable_rerank and search_kb.enable_rerank,
                rerank_top_k=config.rerank_top_k,
            )

            all_results.extend(results)
            all_sources.extend(
                {r.metadata.get("file_name", "Unknown") for r in results}
            )

        # Sort and limit
        all_results.sort(key=lambda x: x.score, reverse=True)
        all_results = all_results[: config.rerank_top_k or config.top_k]

        # Generate if LLM model ID provided
        answer = ""
        if request.llm_model_id:
            # Generate using the primary KB's collection
            # Note: multi-KB RAG re-retrieves from the primary KB
            answer, results, sources = await rag_service.rag(
                query=request.query,
                collection_name=kb.collection_name,
                user_id=kb.user_id,
                top_k=config.top_k,
                retrieval_mode=config.retrieval_mode,
                vector_weight=config.vector_weight,
                similarity_threshold=config.similarity_threshold,
                enable_rerank=config.enable_rerank,
                rerank_top_k=config.rerank_top_k,
                prompt_template=request.prompt,
                conversation_history=request.history,
            )
            # Update sources to include all KBs' sources
            all_sources = list(set(all_sources + sources))
        else:
            # Just return retrieved content
            answer = "\n\n".join(
                [f"[Score: {r.score:.3f}] {r.content[:300]}..." for r in all_results]
            )

        return RAGResponse(
            answer=answer,
            results=all_results,
            sources=list(set(all_sources)),
            query=request.query,
        )

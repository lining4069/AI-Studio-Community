"""
Knowledge Base API router.

Provides endpoints for:
- Knowledge Base CRUD
- File upload and management
- File indexing pipeline
- Retrieval and RAG
"""

import os
from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
)
from loguru import logger

from app.common.responses import APIResponse, PageData
from app.dependencies import CurrentUser, KBFileStorage
from app.dependencies.infras import DBAsyncSession
from app.modules.knowledge_base.repository import (
    KbChunkRepository,
    KbDocumentRepository,
    KbFileRepository,
)
from app.modules.knowledge_base.schema import (
    KbDocumentCreate,
    KbDocumentResponse,
    KbDocumentUpdate,
    KbFileResponse,
    RAGRequest,
    RAGResponse,
    RetrievalRequest,
    RetrievalResponse,
)
from app.modules.knowledge_base.service import KnowledgeBaseService

router = APIRouter()


# ============================================================================
# Repository & Service Dependencies
# ============================================================================


def get_kb_document_repository(db: DBAsyncSession) -> KbDocumentRepository:
    """Get KB Document repository"""
    return KbDocumentRepository(db)


def get_kb_file_repository(db: DBAsyncSession) -> KbFileRepository:
    """Get KB File repository"""
    return KbFileRepository(db)


def get_kb_chunk_repository(db: DBAsyncSession) -> KbChunkRepository:
    """Get KB Chunk repository"""
    return KbChunkRepository(db)


def get_kb_service(
    doc_repo: Annotated[KbDocumentRepository, Depends(get_kb_document_repository)],
    file_repo: Annotated[KbFileRepository, Depends(get_kb_file_repository)],
    chunk_repo: Annotated[KbChunkRepository, Depends(get_kb_chunk_repository)],
) -> KnowledgeBaseService:
    """Get Knowledge Base service"""
    return KnowledgeBaseService(
        doc_repo=doc_repo,
        file_repo=file_repo,
        chunk_repo=chunk_repo,
    )


# Type aliases for dependency injection
KBServiceDep = Annotated[KnowledgeBaseService, Depends(get_kb_service)]


# ============================================================================
# Knowledge Base CRUD Endpoints
# ============================================================================


@router.post("", response_model=APIResponse[KbDocumentResponse], status_code=201)
async def create_knowledge_base(
    data: KbDocumentCreate,
    current_user: CurrentUser,
    service: KBServiceDep,
):
    """Create a new Knowledge Base"""
    kb = await service.create_kb(current_user.id, data)
    return APIResponse(data=kb, message="创建成功")


@router.get("", response_model=APIResponse[PageData[KbDocumentResponse]])
async def list_knowledge_bases(
    current_user: CurrentUser,
    service: KBServiceDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """List all Knowledge Bases for the current user"""
    items, total = await service.list_kbs(current_user.id, page, page_size)
    return APIResponse(
        data=PageData(items=items, total=total, page=page, page_size=page_size)
    )


@router.get("/{kb_id}", response_model=APIResponse[KbDocumentResponse])
async def get_knowledge_base(
    kb_id: str,
    current_user: CurrentUser,
    service: KBServiceDep,
):
    """Get a specific Knowledge Base"""
    kb = await service.get_kb(kb_id, current_user.id)
    return APIResponse(data=kb)


@router.put("/{kb_id}", response_model=APIResponse[KbDocumentResponse])
async def update_knowledge_base(
    kb_id: str,
    data: KbDocumentUpdate,
    current_user: CurrentUser,
    service: KBServiceDep,
):
    """Update a Knowledge Base"""
    kb = await service.update_kb(kb_id, current_user.id, data)
    return APIResponse(data=kb, message="更新成功")


@router.delete("/{kb_id}", status_code=204)
async def delete_knowledge_base(
    kb_id: str,
    current_user: CurrentUser,
    service: KBServiceDep,
):
    """Delete a Knowledge Base and all its files/chunks"""
    await service.delete_kb(kb_id, current_user.id)


# ============================================================================
# File Management Endpoints
# ============================================================================


@router.post(
    "/{kb_id}/files",
    response_model=APIResponse[KbFileResponse],
    status_code=201,
)
async def upload_file(
    kb_id: str,
    current_user: CurrentUser,
    service: KBServiceDep,
    file_storage: KBFileStorage,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    """
    Upload a file to a Knowledge Base.

    Supports: TXT, MD, PDF, DOCX, CSV, JSONL
    Max file size: 50MB
    """
    # Validate file size (50MB)
    MAX_FILE_SIZE = 50 * 1024 * 1024
    file.file.seek(0, 2)  # Seek to end
    size = file.file.tell()
    file.file.seek(0)  # Reset to start

    if size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max size is {MAX_FILE_SIZE // (1024 * 1024)}MB",
        )

    # Validate file type
    content_type = file.content_type or "application/octet-stream"

    # Check extension as fallback
    filename = file.filename or "unknown"
    ext = os.path.splitext(filename)[1].lower()
    ext_to_type = {
        ".txt": "text/plain",
        ".md": "text/markdown",
        ".markdown": "text/markdown",
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".doc": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".csv": "text/csv",
        ".jsonl": "application/jsonl",
    }

    file_type = ext_to_type.get(ext, content_type)

    # Read file content
    content = await file.read()

    # Save file to storage
    kb = await service.get_kb(kb_id, current_user.id)
    file_path = await file_storage.save(
        content,
        kb_id,
        user_id=kb.user_id,
        filename=filename,
    )

    # Create file record
    kb_file = await service.add_file(
        user_id=current_user.id,
        kb_id=kb_id,
        file_name=filename,
        file_path=file_path,
        file_size=size,
        file_type=file_type,
        content=content,
    )

    # Schedule background indexing task
    background_tasks.add_task(
        index_file_background,
        kb_file.id,
        current_user.id,
        service,
    )

    return APIResponse(data=kb_file, message="文件上传成功，正在后台索引")


async def index_file_background(
    file_id: str, user_id: int, service: KnowledgeBaseService
):
    """Background task to index a file"""
    try:
        await service.index_file(file_id, user_id)
        logger.info(f"Successfully indexed file {file_id}")
    except Exception as e:
        logger.error(f"Failed to index file {file_id}: {e}")


@router.get("/{kb_id}/files", response_model=APIResponse[PageData[KbFileResponse]])
async def list_files(
    kb_id: str,
    current_user: CurrentUser,
    service: KBServiceDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
):
    """List files in a Knowledge Base"""
    items, total = await service.list_files(
        kb_id, current_user.id, page, page_size, status
    )
    return APIResponse(
        data=PageData(items=items, total=total, page=page, page_size=page_size)
    )


@router.get("/{kb_id}/files/{file_id}", response_model=APIResponse[KbFileResponse])
async def get_file(
    kb_id: str,
    file_id: str,
    current_user: CurrentUser,
    service: KBServiceDep,
):
    """Get a specific file"""
    # Verify KB access
    await service.get_kb(kb_id, current_user.id)
    file = await service.get_file(file_id, current_user.id)
    return APIResponse(data=file)


@router.delete("/{kb_id}/files/{file_id}", status_code=204)
async def delete_file(
    kb_id: str,
    file_id: str,
    current_user: CurrentUser,
    service: KBServiceDep,
):
    """Delete a file and its chunks"""
    # Verify KB access
    await service.get_kb(kb_id, current_user.id)
    await service.delete_file(file_id, current_user.id)


# ============================================================================
# Indexing Endpoints
# ============================================================================


@router.post("/{kb_id}/files/{file_id}/index", status_code=202)
async def index_file(
    kb_id: str,
    file_id: str,
    current_user: CurrentUser,
    service: KBServiceDep,
    background_tasks: BackgroundTasks,
):
    """
    Trigger file indexing (re-index).

    Indexes the file into the vector store.
    """
    # Verify KB and file access
    await service.get_kb(kb_id, current_user.id)
    await service.get_file(file_id, current_user.id)

    # Run in background
    background_tasks.add_task(
        index_file_background,
        file_id,
        current_user.id,
        service,
    )

    return APIResponse(message="索引任务已提交")


# ============================================================================
# Retrieval & RAG Endpoints
# ============================================================================


@router.post("/rag", response_model=APIResponse[RAGResponse])
async def rag(
    request: RAGRequest,
    current_user: CurrentUser,
    service: KBServiceDep,
):
    """
    Full RAG pipeline or pure retrieval.

    If llm_model_id is provided: retrieve + generate answer (full RAG)
    If llm_model_id is not provided: pure retrieval of relevant chunks
    """
    response = await service.rag(current_user.id, request)
    return APIResponse(data=response)


@router.post("/retrieve", response_model=APIResponse[RetrievalResponse])
async def retrieve(
    request: RetrievalRequest,
    current_user: CurrentUser,
    service: KBServiceDep,
):
    """
    Pure retrieval endpoint.

    Retrieve relevant chunks from knowledge base(s) without LLM generation.
    """
    response = await service.retrieve(current_user.id, request)
    return APIResponse(data=response)

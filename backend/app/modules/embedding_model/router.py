"""
Embedding Model API router.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.dependencies import CurrentUser, DBAsyncSession
from app.modules.embedding_model.repository import EmbeddingModelRepository
from app.modules.embedding_model.schema import (
    EmbeddingModelCreate,
    EmbeddingModelListResponse,
    EmbeddingModelResponse,
    EmbeddingModelUpdate,
)
from app.modules.embedding_model.service import EmbeddingModelService

router = APIRouter()


def get_embedding_model_repository(
    db: DBAsyncSession,
) -> EmbeddingModelRepository:
    """Get Embedding Model repository"""
    return EmbeddingModelRepository(db)


def get_embedding_model_service(
    repo: Annotated[EmbeddingModelRepository, Depends(get_embedding_model_repository)],
) -> EmbeddingModelService:
    """Get Embedding Model service"""
    return EmbeddingModelService(repo)


@router.post("", response_model=EmbeddingModelResponse, status_code=201)
async def create_embedding_model(
    data: EmbeddingModelCreate,
    current_user: CurrentUser,
    service: EmbeddingModelService,
):
    """Create a new Embedding model configuration"""
    model = await service.create_model(current_user.id, data)
    return model


@router.get("", response_model=EmbeddingModelListResponse)
async def list_embedding_models(
    current_user: CurrentUser,
    service: EmbeddingModelService,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """List all Embedding models for the current user"""
    items, total = await service.list_models(current_user.id, page, page_size)
    return EmbeddingModelListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/default", response_model=EmbeddingModelResponse)
async def get_default_embedding_model(
    current_user: CurrentUser,
    service: EmbeddingModelService,
):
    """Get the default Embedding model"""
    model = await service.get_default_model(current_user.id)
    if not model:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=404, detail="No default Embedding model configured"
        )
    return model


@router.get("/{model_id}", response_model=EmbeddingModelResponse)
async def get_embedding_model(
    model_id: str,
    current_user: CurrentUser,
    service: EmbeddingModelService,
):
    """Get a specific Embedding model"""
    model = await service.get_model(model_id, current_user.id)
    return model


@router.put("/{model_id}", response_model=EmbeddingModelResponse)
async def update_embedding_model(
    model_id: str,
    data: EmbeddingModelUpdate,
    current_user: CurrentUser,
    service: EmbeddingModelService,
):
    """Update an Embedding model"""
    model = await service.update_model(model_id, current_user.id, data)
    return model


@router.delete("/{model_id}", status_code=204)
async def delete_embedding_model(
    model_id: str,
    current_user: CurrentUser,
    service: EmbeddingModelService,
):
    """Delete an Embedding model"""
    await service.delete_model(model_id, current_user.id)

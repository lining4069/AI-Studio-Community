"""
Embedding Model API router.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.common.responses import APIResponse, PageData
from app.dependencies import CurrentUser
from app.dependencies.infras import DBAsyncSession
from app.modules.embedding_model.repository import EmbeddingModelRepository
from app.modules.embedding_model.schema import (
    EmbeddingModelCreate,
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


EmbeddingModelServiceDep = Annotated[EmbeddingModelService, Depends(get_embedding_model_service)]


@router.post("", response_model=APIResponse[EmbeddingModelResponse], status_code=201)
async def create_embedding_model(
    data: EmbeddingModelCreate,
    current_user: CurrentUser,
    service: EmbeddingModelServiceDep,
):
    """Create a new Embedding model configuration"""
    model = await service.create_model(current_user.id, data)
    return APIResponse(data=model, message="创建成功")


@router.get("", response_model=APIResponse[PageData[EmbeddingModelResponse]])
async def list_embedding_models(
    current_user: CurrentUser,
    service: EmbeddingModelServiceDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """List all Embedding models for the current user"""
    return APIResponse(data=await service.list_models(current_user.id, page, page_size))


@router.get("/default", response_model=APIResponse[EmbeddingModelResponse])
async def get_default_embedding_model(
    current_user: CurrentUser,
    service: EmbeddingModelServiceDep,
):
    """Get the default Embedding model"""
    model = await service.get_default_model(current_user.id)
    if not model:
        raise HTTPException(
            status_code=404, detail="No default Embedding model configured"
        )
    return APIResponse(data=model)


@router.get("/{model_id}", response_model=APIResponse[EmbeddingModelResponse])
async def get_embedding_model(
    model_id: str,
    current_user: CurrentUser,
    service: EmbeddingModelServiceDep,
):
    """Get a specific Embedding model"""
    return APIResponse(data=await service.get_model(model_id, current_user.id))


@router.put("/{model_id}", response_model=APIResponse[EmbeddingModelResponse])
async def update_embedding_model(
    model_id: str,
    data: EmbeddingModelUpdate,
    current_user: CurrentUser,
    service: EmbeddingModelServiceDep,
):
    """Update an Embedding model"""
    return APIResponse(data=await service.update_model(model_id, current_user.id, data))


@router.delete("/{model_id}", status_code=204)
async def delete_embedding_model(
    model_id: str,
    current_user: CurrentUser,
    service: EmbeddingModelServiceDep,
):
    """Delete an Embedding model"""
    await service.delete_model(model_id, current_user.id)

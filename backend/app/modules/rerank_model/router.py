"""
Rerank Model API router.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.dependencies import CurrentUser
from app.dependencies.infras import DBAsyncSession
from app.modules.rerank_model.repository import RerankModelRepository
from app.modules.rerank_model.schema import (
    RerankModelCreate,
    RerankModelListResponse,
    RerankModelResponse,
    RerankModelUpdate,
)
from app.modules.rerank_model.service import RerankModelService

router = APIRouter()


def get_rerank_model_repository(
    db: DBAsyncSession,
) -> RerankModelRepository:
    """Get Rerank Model repository"""
    return RerankModelRepository(db)


def get_rerank_model_service(
    repo: Annotated[RerankModelRepository, Depends(get_rerank_model_repository)],
) -> RerankModelService:
    """Get Rerank Model service"""
    return RerankModelService(repo)


@router.post("", response_model=RerankModelResponse, status_code=201)
async def create_rerank_model(
    data: RerankModelCreate,
    current_user: CurrentUser,
    service: RerankModelService,
):
    """Create a new Rerank model configuration"""
    model = await service.create_model(current_user.id, data)
    return model


@router.get("", response_model=RerankModelListResponse)
async def list_rerank_models(
    current_user: CurrentUser,
    service: RerankModelService,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """List all Rerank models for the current user"""
    items, total = await service.list_models(current_user.id, page, page_size)
    return RerankModelListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/default", response_model=RerankModelResponse)
async def get_default_rerank_model(
    current_user: CurrentUser,
    service: RerankModelService,
):
    """Get the default Rerank model"""
    model = await service.get_default_model(current_user.id)
    if not model:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=404, detail="No default Rerank model configured"
        )
    return model


@router.get("/{model_id}", response_model=RerankModelResponse)
async def get_rerank_model(
    model_id: str,
    current_user: CurrentUser,
    service: RerankModelService,
):
    """Get a specific Rerank model"""
    model = await service.get_model(model_id, current_user.id)
    return model


@router.put("/{model_id}", response_model=RerankModelResponse)
async def update_rerank_model(
    model_id: str,
    data: RerankModelUpdate,
    current_user: CurrentUser,
    service: RerankModelService,
):
    """Update a Rerank model"""
    model = await service.update_model(model_id, current_user.id, data)
    return model


@router.delete("/{model_id}", status_code=204)
async def delete_rerank_model(
    model_id: str,
    current_user: CurrentUser,
    service: RerankModelService,
):
    """Delete a Rerank model"""
    await service.delete_model(model_id, current_user.id)

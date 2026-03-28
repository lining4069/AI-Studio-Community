"""
LLM Model API router.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.dependencies import CurrentUser
from app.dependencies.infras import DBAsyncSession
from app.modules.llm_model.repository import LlmModelRepository
from app.modules.llm_model.schema import (
    LlmModelCreate,
    LlmModelListResponse,
    LlmModelResponse,
    LlmModelUpdate,
)
from app.modules.llm_model.service import LlmModelService

router = APIRouter()


def get_llm_model_repository(
    db: DBAsyncSession,
) -> LlmModelRepository:
    """Get LLM Model repository"""
    return LlmModelRepository(db)


def get_llm_model_service(
    repo: Annotated[LlmModelRepository, Depends(get_llm_model_repository)],
) -> LlmModelService:
    """Get LLM Model service"""
    return LlmModelService(repo)


@router.post("", response_model=LlmModelResponse, status_code=201)
async def create_llm_model(
    data: LlmModelCreate,
    current_user: CurrentUser,
    service: LlmModelService,
):
    """Create a new LLM model configuration"""
    model = await service.create_model(current_user.id, data)
    return model


@router.get("", response_model=LlmModelListResponse)
async def list_llm_models(
    current_user: CurrentUser,
    service: LlmModelService,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """List all LLM models for the current user"""
    items, total = await service.list_models(current_user.id, page, page_size)
    return LlmModelListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/default", response_model=LlmModelResponse)
async def get_default_llm_model(
    current_user: CurrentUser,
    service: LlmModelService,
):
    """Get the default LLM model"""
    model = await service.get_default_model(current_user.id)
    if not model:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="No default LLM model configured")
    return model


@router.get("/{model_id}", response_model=LlmModelResponse)
async def get_llm_model(
    model_id: str,
    current_user: CurrentUser,
    service: LlmModelService,
):
    """Get a specific LLM model"""
    model = await service.get_model(model_id, current_user.id)
    return model


@router.put("/{model_id}", response_model=LlmModelResponse)
async def update_llm_model(
    model_id: str,
    data: LlmModelUpdate,
    current_user: CurrentUser,
    service: LlmModelService,
):
    """Update a LLM model"""
    model = await service.update_model(model_id, current_user.id, data)
    return model


@router.delete("/{model_id}", status_code=204)
async def delete_llm_model(
    model_id: str,
    current_user: CurrentUser,
    service: LlmModelService,
):
    """Delete a LLM model"""
    await service.delete_model(model_id, current_user.id)

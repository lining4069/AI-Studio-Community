"""
Rerank Model Pydantic schemas.
"""
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict

from app.modules.rerank_model.models import RerankType


class RerankModelBase(BaseModel):
    """Base schema for Rerank model"""
    name: str = Field(..., min_length=1, max_length=255)
    type: RerankType = Field(default=RerankType.OPENAI_COMPATIBLE)
    model_name: Optional[str] = Field(None, max_length=255)
    base_url: Optional[str] = Field(None, max_length=500)
    api_key: Optional[str] = Field(None)
    top_n: Optional[int] = Field(None, gt=0)
    is_enabled: bool = Field(default=True)
    is_default: bool = Field(default=False)
    description: Optional[str] = None


class RerankModelCreate(RerankModelBase):
    """Schema for creating Rerank model"""
    pass


class RerankModelUpdate(BaseModel):
    """Schema for updating Rerank model"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    type: Optional[RerankType] = None
    model_name: Optional[str] = Field(None, max_length=255)
    base_url: Optional[str] = Field(None, max_length=500)
    api_key: Optional[str] = None
    top_n: Optional[int] = Field(None, gt=0)
    is_enabled: Optional[bool] = None
    is_default: Optional[bool] = None
    description: Optional[str] = None


class RerankModelResponse(RerankModelBase):
    """Schema for Rerank model response"""
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: int
    encrypted_api_key: Optional[str] = None
    api_key: Optional[str] = Field(None, exclude=True)
    created_at: datetime
    updated_at: datetime


class RerankModelListResponse(BaseModel):
    """Schema for paginated Rerank model list"""
    items: List[RerankModelResponse]
    total: int
    page: int
    page_size: int

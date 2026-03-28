"""
Embedding Model Pydantic schemas.
"""
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict

from app.modules.embedding_model.models import EmbeddingType


class EmbeddingModelBase(BaseModel):
    """Base schema for Embedding model"""
    name: str = Field(..., min_length=1, max_length=255)
    type: EmbeddingType = Field(default=EmbeddingType.OPENAI_COMPATIBLE)

    # API mode fields
    model_name: Optional[str] = Field(None, max_length=255)
    endpoint: Optional[str] = Field(None, max_length=500)
    api_key: Optional[str] = Field(None)

    # Local mode fields
    local_model_path: Optional[str] = Field(None, max_length=500)

    # Common fields
    dimension: Optional[int] = Field(None, gt=0)
    batch_size: int = Field(default=10, gt=0)

    is_enabled: bool = Field(default=True)
    is_default: bool = Field(default=False)
    description: Optional[str] = None


class EmbeddingModelCreate(EmbeddingModelBase):
    """Schema for creating Embedding model"""
    pass


class EmbeddingModelUpdate(BaseModel):
    """Schema for updating Embedding model"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    type: Optional[EmbeddingType] = None
    model_name: Optional[str] = Field(None, max_length=255)
    endpoint: Optional[str] = Field(None, max_length=500)
    api_key: Optional[str] = None
    local_model_path: Optional[str] = Field(None, max_length=500)
    dimension: Optional[int] = Field(None, gt=0)
    batch_size: Optional[int] = Field(None, gt=0)
    is_enabled: Optional[bool] = None
    is_default: Optional[bool] = None
    description: Optional[str] = None


class EmbeddingModelResponse(EmbeddingModelBase):
    """Schema for Embedding model response"""
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: int
    encrypted_api_key: Optional[str] = None
    api_key: Optional[str] = Field(None, exclude=True)
    created_at: datetime
    updated_at: datetime


class EmbeddingModelListResponse(BaseModel):
    """Schema for paginated Embedding model list"""
    items: List[EmbeddingModelResponse]
    total: int
    page: int
    page_size: int

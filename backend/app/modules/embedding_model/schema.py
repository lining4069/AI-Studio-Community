"""
Embedding Model Pydantic schemas.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.embedding_model.models import EmbeddingType


class EmbeddingModelBase(BaseModel):
    """Base schema for Embedding model"""

    name: str = Field(..., min_length=1, max_length=255)
    type: EmbeddingType = Field(default=EmbeddingType.OPENAI_COMPATIBLE)

    # API mode fields
    model_name: str | None = Field(None, max_length=255)
    endpoint: str | None = Field(None, max_length=500)
    api_key: str | None = Field(None)

    # Local mode fields
    local_model_path: str | None = Field(None, max_length=500)

    # Common fields
    dimension: int | None = Field(None, gt=0)
    batch_size: int = Field(default=10, gt=0)

    is_enabled: bool = Field(default=True)
    is_default: bool = Field(default=False)
    description: str | None = None


class EmbeddingModelCreate(EmbeddingModelBase):
    """Schema for creating Embedding model"""

    pass


class EmbeddingModelUpdate(BaseModel):
    """Schema for updating Embedding model"""

    name: str | None = Field(None, min_length=1, max_length=255)
    type: EmbeddingType | None = None
    model_name: str | None = Field(None, max_length=255)
    endpoint: str | None = Field(None, max_length=500)
    api_key: str | None = Field(None, exclude=True)
    local_model_path: str | None = Field(None, max_length=500)
    dimension: int | None = Field(None, gt=0)
    batch_size: int | None = Field(None, gt=0)
    is_enabled: bool | None = None
    is_default: bool | None = None
    description: str | None = None


class EmbeddingModelResponse(EmbeddingModelBase):
    """Schema for Embedding model response"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: int
    encrypted_api_key: str | None = None
    api_key: str | None = Field(None, exclude=True)
    is_dimensionable: bool | None = None
    created_at: datetime
    updated_at: datetime


class EmbeddingModelListResponse(BaseModel):
    """Schema for paginated Embedding model list"""

    items: list[EmbeddingModelResponse]
    total: int
    page: int
    page_size: int

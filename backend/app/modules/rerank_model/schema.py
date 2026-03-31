"""
Rerank Model Pydantic schemas.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RerankModelBase(BaseModel):
    """Base schema for Rerank model"""

    name: str = Field(..., min_length=1, max_length=255)
    provider: str = Field(default="openai_compatible")
    model_name: str | None = Field(None, max_length=255)
    base_url: str | None = Field(None, max_length=500)
    api_key: str | None = Field(None)
    top_n: int | None = Field(None, gt=0)
    is_enabled: bool = Field(default=True)
    is_default: bool = Field(default=False)
    description: str | None = None


class RerankModelCreate(RerankModelBase):
    """Schema for creating Rerank model"""

    pass


class RerankModelUpdate(BaseModel):
    """Schema for updating Rerank model"""

    name: str | None = Field(None, min_length=1, max_length=255)
    provider: str | None = None
    model_name: str | None = Field(None, max_length=255)
    base_url: str | None = Field(None, max_length=500)
    api_key: str | None = Field(None, exclude=True)
    top_n: int | None = Field(None, gt=0)
    is_enabled: bool | None = None
    is_default: bool | None = None
    description: str | None = None


class RerankModelResponse(RerankModelBase):
    """Schema for Rerank model response"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: int
    encrypted_api_key: str | None = None
    api_key: str | None = Field(None, exclude=True)
    created_at: datetime
    updated_at: datetime


class RerankModelListResponse(BaseModel):
    """Schema for paginated Rerank model list"""

    items: list[RerankModelResponse]
    total: int
    page: int
    page_size: int

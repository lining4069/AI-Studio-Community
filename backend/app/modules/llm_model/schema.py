"""
LLM Model Pydantic schemas for request/response validation.
"""
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict


class LlmModelBase(BaseModel):
    """Base schema for LLM model"""
    name: str = Field(..., min_length=1, max_length=255, description="LLM model display name")
    provider: str = Field(
        default="openai_compatible",
        description="Provider type: openai_compatible, dashscope"
    )
    model_name: str = Field(..., min_length=1, max_length=255, description="Actual model name")
    base_url: Optional[str] = Field(None, description="API base URL")
    api_key: Optional[str] = Field(None, description="API key (will be encrypted)")
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, gt=0)
    context_window: int = Field(default=8000, gt=0)
    support_vision: bool = Field(default=False)
    support_function_calling: bool = Field(default=True)
    is_enabled: bool = Field(default=True)
    is_default: bool = Field(default=False)
    description: Optional[str] = None


class LlmModelCreate(LlmModelBase):
    """Schema for creating LLM model"""
    pass


class LlmModelUpdate(BaseModel):
    """Schema for updating LLM model"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    provider: Optional[str] = None
    model_name: Optional[str] = Field(None, min_length=1, max_length=255)
    base_url: Optional[str] = None
    api_key: Optional[str] = Field(None, description="New API key (will be re-encrypted)")
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, gt=0)
    context_window: Optional[int] = Field(None, gt=0)
    support_vision: Optional[bool] = None
    support_function_calling: Optional[bool] = None
    is_enabled: Optional[bool] = None
    is_default: Optional[bool] = None
    description: Optional[str] = None


class LlmModelResponse(LlmModelBase):
    """Schema for LLM model response"""
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: int
    encrypted_api_key: Optional[str] = None
    api_key: Optional[str] = Field(None, exclude=True, description="Never exposed in responses")
    created_at: datetime
    updated_at: datetime


class LlmModelListResponse(BaseModel):
    """Schema for paginated LLM model list"""
    items: List[LlmModelResponse]
    total: int
    page: int
    page_size: int

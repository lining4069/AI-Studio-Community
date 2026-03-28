"""
LLM Model Pydantic schemas for request/response validation.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LlmModelBase(BaseModel):
    """Base schema for LLM model"""

    name: str = Field(
        ..., min_length=1, max_length=255, description="LLM model display name"
    )
    provider: str = Field(
        default="openai_compatible",
        description="Provider type: openai_compatible, dashscope",
    )
    model_name: str = Field(
        ..., min_length=1, max_length=255, description="Actual model name"
    )
    base_url: str | None = Field(None, description="API base URL")
    api_key: str | None = Field(None, description="API key (will be encrypted)")
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    max_tokens: int | None = Field(None, gt=0)
    context_window: int = Field(default=8000, gt=0)
    support_vision: bool = Field(default=False)
    support_function_calling: bool = Field(default=True)
    is_enabled: bool = Field(default=True)
    is_default: bool = Field(default=False)
    description: str | None = None


class LlmModelCreate(LlmModelBase):
    """Schema for creating LLM model"""

    pass


class LlmModelUpdate(BaseModel):
    """Schema for updating LLM model"""

    name: str | None = Field(None, min_length=1, max_length=255)
    provider: str | None = None
    model_name: str | None = Field(None, min_length=1, max_length=255)
    base_url: str | None = None
    api_key: str | None = Field(None, description="New API key (will be re-encrypted)")
    temperature: float | None = Field(None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(None, gt=0)
    context_window: int | None = Field(None, gt=0)
    support_vision: bool | None = None
    support_function_calling: bool | None = None
    is_enabled: bool | None = None
    is_default: bool | None = None
    description: str | None = None


class LlmModelResponse(LlmModelBase):
    """Schema for LLM model response"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: int
    encrypted_api_key: str | None = None
    api_key: str | None = Field(
        None, exclude=True, description="Never exposed in responses"
    )
    created_at: datetime
    updated_at: datetime


class LlmModelListResponse(BaseModel):
    """Schema for paginated LLM model list"""

    items: list[LlmModelResponse]
    total: int
    page: int
    page_size: int

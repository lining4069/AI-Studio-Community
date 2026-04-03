"""
Knowledge Base Pydantic schemas.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.knowledge_base.models import RetrievalMode

# ============================================================================
# KbDocument Schemas
# ============================================================================


class KbDocumentBase(BaseModel):
    """Base schema for Knowledge Base"""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    embedding_model_id: str | None = None
    rerank_model_id: str | None = None
    chunk_size: int = Field(default=512, gt=0)
    chunk_overlap: int = Field(default=50, ge=0)
    chunk_mode: str = Field(default="recursive")
    retrieval_mode: RetrievalMode = Field(default=RetrievalMode.HYBRID)
    top_k: int = Field(default=5, gt=0)
    similarity_threshold: float = Field(default=0.0, ge=0)
    vector_weight: float = Field(default=0.7, ge=0, le=1)
    enable_rerank: bool = Field(default=True)
    rerank_top_k: int = Field(default=3, gt=0)


class KbDocumentCreate(KbDocumentBase):
    """Schema for creating Knowledge Base"""

    pass


class KbDocumentUpdate(BaseModel):
    """Schema for updating Knowledge Base"""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    embedding_model_id: str | None = None
    rerank_model_id: str | None = None
    chunk_size: int | None = Field(None, gt=0)
    chunk_overlap: int | None = Field(None, ge=0)
    chunk_mode: str | None = None
    retrieval_mode: RetrievalMode | None = None
    top_k: int | None = Field(None, gt=0)
    similarity_threshold: float | None = Field(None, ge=0)
    vector_weight: float | None = Field(None, ge=0, le=1)
    enable_rerank: bool | None = None
    rerank_top_k: int | None = Field(None, gt=0)
    is_active: bool | None = None


class KbDocumentResponse(KbDocumentBase):
    """Schema for Knowledge Base response"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: int
    collection_name: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class KbDocumentListResponse(BaseModel):
    """Schema for paginated Knowledge Base list"""

    items: list[KbDocumentResponse]
    total: int
    page: int
    page_size: int


# ============================================================================
# KbFile Schemas
# ============================================================================


class KbFileBase(BaseModel):
    """Base schema for Knowledge Base File"""

    file_name: str
    file_size: int = 0
    file_type: str | None = None


class KbFileResponse(KbFileBase):
    """Schema for Knowledge Base File response"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: int
    kb_id: str
    file_path: str
    file_md5: str | None = None
    status: str
    chunk_count: int
    failed_reason: str | None = None
    metadata: dict = Field(default_factory=dict, validation_alias="file_metadata")
    created_at: datetime
    updated_at: datetime

    @field_validator("metadata", check_fields=False, mode="before")
    @classmethod
    def _ensure_dict(cls, v):
        if not isinstance(v, dict):
            return {}
        return v


class KbFileListResponse(BaseModel):
    """Schema for paginated Knowledge Base File list"""

    items: list[KbFileResponse]
    total: int
    page: int
    page_size: int


# ============================================================================
# RAG / Retrieval Schemas
# ============================================================================


class RetrievalConfig(BaseModel):
    """Retrieval configuration schema"""

    retrieval_mode: RetrievalMode = Field(default=RetrievalMode.HYBRID)
    top_k: int = Field(default=5, gt=0)
    similarity_threshold: float = Field(default=0.0, ge=0)
    vector_weight: float = Field(default=0.7, ge=0, le=1)
    enable_rerank: bool = Field(default=True)
    rerank_top_k: int = Field(default=3, gt=0)


class RetrievalRequest(BaseModel):
    """Schema for retrieval request"""

    query: str = Field(..., min_length=1, description="Query text")
    kb_ids: list[str] = Field(..., min_length=1, description="单库或多库搜索")
    config: RetrievalConfig | None = Field(
        default_factory=RetrievalConfig, description="Retrieval configuration"
    )


class RetrievalResult(BaseModel):
    """Single retrieval result"""

    chunk_id: str
    content: str
    score: float
    metadata: dict = Field(default_factory=dict)


class RetrievalResponse(BaseModel):
    """Schema for retrieval response"""

    results: list[RetrievalResult]
    query: str
    total: int


class RAGRequest(RetrievalRequest):
    """Schema for RAG request (retrieval + LLM generation)"""

    llm_model_id: str | None = Field(
        None,
        description="LLM model ID for answer generation. If not provided, only retrieval is performed.",
    )
    prompt: str | None = Field(
        None,
        description="Custom prompt template. Use {context} and {question} as placeholders.",
    )
    history: list[dict] | None = Field(
        default_factory=list, description="Conversation history for multi-turn RAG"
    )


class RAGResponse(BaseModel):
    """Schema for RAG response (with LLM generation)"""

    answer: str
    results: list[RetrievalResult]
    sources: list[str] = Field(
        default_factory=list, description="Source file names used in generation"
    )
    query: str

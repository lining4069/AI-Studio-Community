"""
Knowledge Base database models.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.common.base import Base
from app.utils.datetime_utils import now_utc


class RetrievalMode(StrEnum):
    """Retrieval mode enum"""

    DENSE = "dense"  # Only vector search
    SPARSE = "sparse"  # Only BM25 keyword search
    HYBRID = "hybrid"  # Both vector + BM25


class ChunkStatus(StrEnum):
    """Chunk processing status"""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# ============================================================================
# Knowledge Base Document
# ============================================================================


class KbDocument(Base):
    """Knowledge Base Document Entity"""

    __tablename__ = "kb_documents"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: uuid.uuid4().hex
    )
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Model configuration - references embedding_model by id
    embedding_model_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("embedding_models.id", ondelete="SET NULL"),
        nullable=True,
    )
    rerank_model_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("rerank_models.id", ondelete="SET NULL"), nullable=True
    )

    # Chunk configuration
    chunk_size: Mapped[int] = mapped_column(Integer, default=512)
    chunk_overlap: Mapped[int] = mapped_column(Integer, default=50)
    chunk_mode: Mapped[str] = mapped_column(String(50), default="recursive")

    # Retrieval configuration
    retrieval_mode: Mapped[str] = mapped_column(
        String(20), default=RetrievalMode.HYBRID.value
    )
    top_k: Mapped[int] = mapped_column(Integer, default=5)
    similarity_threshold: Mapped[float] = mapped_column(default=0.0)
    vector_weight: Mapped[float] = mapped_column(default=0.7)
    enable_rerank: Mapped[bool] = mapped_column(Boolean, default=True)
    rerank_top_k: Mapped[int] = mapped_column(Integer, default=3)

    # ChromaDB collection name for this KB
    collection_name: Mapped[str] = mapped_column(String(255), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False
    )

    def __repr__(self):
        return f"<KbDocument(id={self.id}, name={self.name})>"


# ============================================================================
# Knowledge Base File
# ============================================================================


class KbFile(Base):
    """Knowledge Base File Entity"""

    __tablename__ = "kb_files"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: uuid.uuid4().hex
    )
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    kb_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("kb_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # File info
    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    file_type: Mapped[str] = mapped_column(String(100), nullable=True)
    file_md5: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Processing status
    status: Mapped[str] = mapped_column(String(20), default=ChunkStatus.PENDING.value)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Metadata from file parsing
    file_metadata: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False
    )

    def __repr__(self):
        return f"<KbFile(id={self.id}, name={self.file_name}, kb_id={self.kb_id})>"



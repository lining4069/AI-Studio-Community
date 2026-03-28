"""
Embedding Model database models.
"""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.common.base import Base


class EmbeddingType(str, Enum):
    """Embedding type enum"""

    OPENAI_COMPATIBLE = "openai_compatible"  # API调用模式
    LOCAL = "local"  # 本地HuggingFace模型


class EmbeddingModel(Base):
    """Embedding Model Entity"""

    __tablename__ = "embedding_models"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: uuid.uuid4().hex
    )
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(
        String(50), nullable=False, default=EmbeddingType.OPENAI_COMPATIBLE.value
    )

    # API mode fields
    model_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    endpoint: Mapped[str | None] = mapped_column(String(500), nullable=True)
    api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    encrypted_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Local mode fields
    local_model_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Common fields
    dimension: Mapped[int | None] = mapped_column(Integer, nullable=True)
    batch_size: Mapped[int] = mapped_column(Integer, default=10)

    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self):
        return f"<EmbeddingModel(id={self.id}, name={self.name}, type={self.type})>"

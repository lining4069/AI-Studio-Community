"""
LLM Model database models.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.common.base import Base
from app.utils.datetime_utils import now_utc


class LLMType(StrEnum):
    """Embedding type enum"""

    OPENAI_COMPATIBLE = "openai_compatible"  # API调用模式
    LOCAL = "local"  # 本地HuggingFace模型


class LlmModel(Base):
    """LLM Model Entity"""

    __tablename__ = "llm_models"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: uuid.uuid4().hex
    )
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(
        String(50), nullable=False, default=LLMType.OPENAI_COMPATIBLE.value
    )
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    encrypted_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)

    temperature: Mapped[float] = mapped_column(default=0.1)
    max_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    context_window: Mapped[int] = mapped_column(Integer, default=8000)

    support_vision: Mapped[bool] = mapped_column(Boolean, default=False)
    support_function_calling: Mapped[bool] = mapped_column(Boolean, default=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)

    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False
    )

    def __repr__(self):
        return f"<LlmModel(id={self.id}, name={self.name}, provider={self.provider})>"

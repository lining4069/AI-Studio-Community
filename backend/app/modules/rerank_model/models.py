"""
Rerank Model database models.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.common.base import Base
from app.utils.datetime_utils import now_utc


class RerankType(StrEnum):
    """Rerank type enum"""

    OPENAI_COMPATIBLE = "openai_compatible"  # Cohere/Jina 等兼容 /v1/rerank 端点
    DASHSCOPE = "dashscope"  # 阿里云 DashScope 文本排序 API


class RerankModel(Base):
    """Rerank Model Entity"""

    __tablename__ = "rerank_models"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: uuid.uuid4().hex
    )
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(
        String(50), nullable=False, default=RerankType.OPENAI_COMPATIBLE.value
    )

    model_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    encrypted_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)

    top_n: Mapped[int | None] = mapped_column(Integer, nullable=True)
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
        return f"<RerankModel(id={self.id}, name={self.name}, type={self.type})>"

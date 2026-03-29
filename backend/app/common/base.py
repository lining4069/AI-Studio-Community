# 跨模块通用代码
from collections.abc import Sequence
from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict
from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.utils.datetime_utils import now_utc


class Base(DeclarativeBase):
    """ORM Base Class"""

    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        nullable=False,
        comment="创建时间",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        onupdate=now_utc,
        nullable=False,
        comment="更新时间",
    )


T = TypeVar("T")


class PageData(BaseModel, Generic[T]):
    """分页数据模型"""

    page_data: Sequence[T]
    total: int
    hasMore: bool

    model_config = ConfigDict(from_attributes=True)


class PageParams(BaseModel):
    """分页参数模型"""

    page: int
    page_size: int

    @property
    def offset(self) -> int:
        """计算偏移量"""
        return (self.page - 1) * self.page_size

    def calc_has_more(self, total: int) -> bool:
        """计算是否有下一页"""
        return self.page * self.page_size < total

# 跨模块通用代码
from collections.abc import Sequence
from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, field_serializer
from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.utils.datetime_utils import format_dt, now_utc


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


class BaseResponseSchema(BaseModel):
    """基础Pydantic模型"""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )

    @field_serializer("*", when_used="json")
    def serialize_datetime(self, value: Any) -> Any:
        """
        统一 datetime 序列化：
        - 转换为 APP_TIMEZONE
        - 输出字符串
        """
        if isinstance(value, datetime):
            return format_dt(value)
        return value


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
    limit: int

    @property
    def offset(self) -> int:
        """计算偏移量"""
        return (self.page - 1) * self.limit

    def calc_has_more(self, total: int) -> bool:
        """计算是否有下一页"""
        return self.page * self.limit < total

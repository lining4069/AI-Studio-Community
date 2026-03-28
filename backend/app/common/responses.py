from typing import Generic, TypeVar

from fastapi import status
from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """通用成功响应模型"""

    code: int = status.HTTP_200_OK
    message: str = "Success Response"
    data: T | None = None

    model_config = ConfigDict(from_attributes=True)

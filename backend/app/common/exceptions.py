# app/common/exceptions.py

import traceback
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from loguru import logger
from starlette import status

from app.core.settings import Settings


# 1. 业务异常类
class BusinessException(Exception):
    """通用业务异常基类"""

    def __init__(self, message: str, code: int = 400):
        self.message = message
        self.code = code


class ValidationException(BusinessException):
    """通用业务校验失败"""

    def __init__(self, message: str):
        super().__init__(message=message, code=400)


class UnauthorizedException(BusinessException):
    """未经认证 (401)"""

    def __init__(self, message: str = "登录状态已失效，请重新登录"):
        super().__init__(message=message, code=401)


class ForbiddenException(BusinessException):
    """权限不足 (403)"""

    def __init__(self, message: str = "您没有权限执行此操作"):
        super().__init__(message=message, code=403)


class NotFoundException(BusinessException):
    """资源不存在 (404)"""

    def __init__(self, resource: str, identifier: Any):
        super().__init__(message=f"{resource} '{identifier}' 不存在", code=404)


class UniqueViolationException(BusinessException):
    """唯一性约束冲突 (400)"""

    def __init__(self, resource: str, identifier: Any):
        super().__init__(
            message=f"{resource} '{identifier}' 已存在，请更换后重试",
            code=400,
        )


class DatabaseOperationException(BusinessException):
    """数据库操作未生效 (如 rowcount=0)"""

    def __init__(self, resource: str, identifier: Any, action: str = "更新"):
        super().__init__(
            message=f"{action}{resource} '{identifier}' 失败，数据可能已被删除或无变动",
            code=400,
        )


class RateLimitException(BusinessException):
    """操作过于频繁"""

    def __init__(self, message: str = "操作过于频繁，请稍后再试"):
        super().__init__(message=message, code=429)


class AIProviderException(BusinessException):
    """AI Provider API 错误"""

    def __init__(self, message: str):
        super().__init__(message=message, code=400)


class AIProviderCapabilityException(BusinessException):
    """AI Provider 不支持该能力"""

    def __init__(self, message: str):
        super().__init__(message=message, code=501)


# 2. 异常处理器
def register_exception_handlers(app: FastAPI, settings: Settings):
    """注册异常处理器"""

    async def business_exception_handler(
        request: Request, exc: BusinessException
    ) -> JSONResponse:
        error_data = None
        if getattr(settings, "DEBUG", False):
            error_data = {
                "error_type": type(exc).__name__,
                "error_detail": str(exc),
                "traceback": traceback.format_exc(),
                "path": str(request.url),
            }
        logger.warning(
            f"BusinessException: path={request.url} code={exc.code} message={exc.message}\n"
            f"{error_data['traceback'] if error_data else ''}"
        )
        return JSONResponse(
            status_code=exc.code,
            content={"code": exc.code, "message": exc.message, "data": error_data},
        )

    async def general_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        error_data = None
        if getattr(settings, "DEBUG", False):
            error_data = {
                "error_type": type(exc).__name__,
                "error_detail": str(exc),
                "traceback": traceback.format_exc(),
                "path": str(request.url),
            }
        logger.error(
            f"Unhandled Exception: path={request.url} type={type(exc).__name__} message={str(exc)}\n"
            f"{error_data['traceback'] if error_data else ''}"
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"code": 500, "message": "服务器内部错误", "data": error_data},
        )

    app.add_exception_handler(BusinessException, business_exception_handler)  # type: ignore
    app.add_exception_handler(Exception, general_exception_handler)

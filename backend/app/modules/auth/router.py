from typing import Annotated

from fastapi import APIRouter, Depends

from app.common.logger import logger
from app.common.responses import APIResponse
from app.dependencies import CurrentUser
from app.dependencies.auth import TokenPayload, get_token_payload
from app.dependencies.services import get_auth_service
from app.modules.auth.schema import (
    RefreshTokenRequest,
    RefreshTokenResponse,
    UserAuthedResponse,
    UserCreateRequest,
    UserLogoutRequest,
)
from app.modules.auth.service import AuthService

router = APIRouter()


@router.post("/register", response_model=APIResponse[UserAuthedResponse])
async def register(
    user_data: UserCreateRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
):
    """
    用户注册
    逻辑：验证用户是否存在 -> 创建用户 -> 生成Token -> 响应结果
    """
    logger.info("接口 用户注册 :'/register' 被访问")
    user_auth_info = await service.register_user(user_data)
    return APIResponse(data=user_auth_info, message="注册成功")


@router.post("/login", response_model=APIResponse[UserAuthedResponse])
async def login(
    user_data: UserCreateRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
):
    """
    用户登录
    逻辑: 验证用户是否存在 -> 验证密码 -> 生成Token -> 响应结果
    """
    logger.info(f"接口 用户登录 :'/login' 被访问,用户{user_data.username}正在尝试登录")
    user_auth_info = await service.login(user_data)
    return APIResponse(data=user_auth_info, message="登录成功")


@router.post("/refresh", response_model=APIResponse[RefreshTokenResponse])
async def refresh(
    data: RefreshTokenRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
):
    """
    刷新 Access Token(带 Rotation)
    """
    logger.info("接口 '/refresh' 被访问")
    result = await service.refresh_token(data)
    return APIResponse(data=result, message="刷新成功")


@router.post("/logout")
async def logout(
    data: UserLogoutRequest,
    token_payload: Annotated[TokenPayload, Depends(get_token_payload)],
    user: CurrentUser,
    service: Annotated[AuthService, Depends(get_auth_service)],
):
    """
    用户登出
    逻辑: 拉黑 access token -> 删除 refresh token -> 删除设备记录
    """
    logger.info("接口 用户登出 :'/logout' 被访问")
    result = await service.logout(data, token_payload)
    return APIResponse(data=result, message="登出成功")

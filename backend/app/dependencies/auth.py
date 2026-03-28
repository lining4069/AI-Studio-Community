import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from redis.asyncio import Redis

from app.common.exceptions import NotFoundException, UnauthorizedException
from app.core.settings import Settings, get_settings
from app.dependencies.infras.cache import get_cache
from app.dependencies.repositories import get_user_repository
from app.modules.users.models import User
from app.modules.users.repository import UserRepository


# Token Payload 数据类
class TokenPayload(BaseModel):
    user_id: int
    token_type: str
    jti: str
    exp: int


security = HTTPBearer()


# 1. 解析 Token（JWT Decode）
async def get_token_payload(
    token: HTTPAuthorizationCredentials = Depends(security),
    settings: Settings = Depends(get_settings),
) -> TokenPayload:
    """
    解析 JWT Token,返回 TokenPayload
    """
    try:
        payload = jwt.decode(
            token.credentials,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except jwt.ExpiredSignatureError as e:
        raise UnauthorizedException("Token 已过期") from e
    except jwt.InvalidTokenError as e:
        raise UnauthorizedException("无效的 Token") from e

    return TokenPayload(
        user_id=int(payload["sub"]),
        token_type=payload["type"],
        jti=payload["jti"],
        exp=payload["exp"],
    )


# 2. 校验 Token（类型 + 黑名单）
async def validate_access_token(
    payload: TokenPayload = Depends(get_token_payload),
    redis: Redis = Depends(get_cache),
    settings: Settings = Depends(get_settings),
) -> TokenPayload:
    """
    校验 Access Token:
    - 类型必须是 access
    - 不在黑名单
    """
    if payload.token_type != "access":
        raise UnauthorizedException("Token 类型错误")

    blacklist_key = settings.TOKEN_BLACKLIST_PROMPT.format(payload.jti)

    if await redis.get(blacklist_key):
        raise UnauthorizedException("Token 已被注销")

    return payload


# 3. 获取用户（数据层）
async def get_user(
    payload: TokenPayload = Depends(validate_access_token),
    repo: UserRepository = Depends(get_user_repository),
) -> User:
    """
    根据 Token 获取用户（仅数据校验）
    """
    user = await repo.get_by_id(payload.user_id)

    if not user or user.is_deleted:
        raise NotFoundException("用户不存在", f"ID: {payload.user_id}")

    return user


# 4. 当前用户（业务层校验）
async def get_current_user(
    user: User = Depends(get_user),
) -> User:
    """
    当前登录用户（完整校验）
    """
    if not user.is_active:
        raise UnauthorizedException("用户已被禁用")

    return user

from dataclasses import dataclass
from datetime import timedelta
from uuid import uuid4

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.common.exceptions import UnauthorizedException
from app.core.settings import Settings
from app.utils.datetime_utils import now_utc

# 使用Argon2id  基于 Argon2 密码哈希算法
ph = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
)


def hash_password(password: str) -> str:
    """密码加密"""
    return ph.hash(password=password)


def verify_password(password: str, hashed_pwd: str) -> bool:
    """密码校验"""
    try:
        ph.verify(hash=hashed_pwd, password=password)
        return True
    except VerifyMismatchError:
        return False


def create_access_token(user_id: int, settings: Settings) -> str:
    """创建Access token"""
    jti = str(uuid4())
    expire = now_utc() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub": str(user_id),
        "type": "access",
        "jti": jti,
        "exp": expire,
    }
    access_token = jwt.encode(
        payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )
    return access_token


def create_refresh_token(
    user_id: int, device_id: str, settings: Settings
) -> tuple[str, str]:
    """创建Refresh token"""
    jti = str(uuid4())
    expire = now_utc() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "jti": jti,
        "exp": expire,
        "device_id": device_id,
    }
    refresh_token = jwt.encode(
        payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )
    return refresh_token, jti


@dataclass
class RefreshTokenPayload:
    user_id: int
    token_type: str
    jti: str
    exp: int
    device_id: str


def decode_refresh_token(refresh_token: str, settings: Settings) -> RefreshTokenPayload:
    """解析Refresh Token"""
    try:
        payload = jwt.decode(
            refresh_token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except jwt.ExpiredSignatureError as e:
        raise UnauthorizedException("Refresh Token 已过期") from e
    except jwt.InvalidTokenError as e:
        raise UnauthorizedException("无效的 Refresh Token") from e

    if payload.get("type") != "refresh":
        raise UnauthorizedException("Token 类型错误")

    return RefreshTokenPayload(
        user_id=int(payload["sub"]),
        token_type=payload["type"],
        jti=payload["jti"],
        exp=payload["exp"],
        device_id=payload["device_id"],
    )

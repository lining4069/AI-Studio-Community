from redis.asyncio import Redis

from app.common.exceptions import (
    NotFoundException,
    UnauthorizedException,
    UniqueViolationException,
    ValidationException,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    verify_password,
)
from app.core.settings import Settings
from app.dependencies.auth import TokenPayload
from app.modules.auth.repository import AuthRepository
from app.modules.auth.schema import (
    RefreshTokenRequest,
    RefreshTokenResponse,
    UserAuthedResponse,
    UserCreateRequest,
    UserLogoutRequest,
    UserLogoutResponse,
)
from app.modules.users.schema import UserResponse
from app.utils.datetime_utils import now_utc


class AuthService:
    def __init__(self, repo: AuthRepository, cache: Redis, settings: Settings):
        self.repo = repo
        self.cache = cache
        self.settings = settings

    async def register_user(self, user_data: UserCreateRequest) -> UserAuthedResponse:
        """用户注册"""
        # 检查用户是否已经存在
        existing_user = await self.repo.get_user_by_username(user_data.username)
        if existing_user:
            raise UniqueViolationException("用户", user_data.username)
        # 创建用户
        user = await self.repo.create_user(user_data)
        # 创建Token
        access_token = create_access_token(user.id, self.settings)
        refresh_token, refresh_jti = create_refresh_token(
            user.id, user_data.device_id, self.settings
        )
        # 缓存到redis
        await self.cache.setex(
            self.settings.REFRESH_TOKEN_PROMPT.format(user.id, user_data.device_id),
            self.settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
            refresh_jti,
        )
        # 记录设备
        await self.cache.sadd(
            self.settings.USER_DEVICES_SET_PROMPT.format(user.id), user_data.device_id
        )
        # 构建,返回UserAuthedResponse
        return UserAuthedResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            userInfo=UserResponse.model_validate(user),
        )

    async def login(self, user_data: UserCreateRequest) -> UserAuthedResponse:
        """用户登录"""
        # 检查用户是否存在
        existing_user = await self.repo.get_user_by_username(user_data.username)
        if not existing_user:
            raise NotFoundException("用户", user_data.username)
        # 验证密码是否正确
        pwd_verify = verify_password(user_data.password, existing_user.password)
        if not pwd_verify:
            raise ValidationException(f"{user_data.username}的密码错误,请检查后重试")
        # 创建Token
        access_token = create_access_token(existing_user.id, self.settings)
        refresh_token, refresh_jti = create_refresh_token(
            existing_user.id, user_data.device_id, self.settings
        )
        # 缓存到redis
        await self.cache.setex(
            self.settings.REFRESH_TOKEN_PROMPT.format(
                existing_user.id, user_data.device_id
            ),
            self.settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
            refresh_jti,
        )
        # 记录设备
        await self.cache.sadd(
            self.settings.USER_DEVICES_SET_PROMPT.format(existing_user.id),
            user_data.device_id,
        )
        # 构建,返回UserAuthedResponse
        return UserAuthedResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            userInfo=UserResponse.model_validate(existing_user),
        )

    async def refresh_token(self, data: RefreshTokenRequest) -> RefreshTokenResponse:
        """
        Refresh Rotation
        """
        payload = decode_refresh_token(data.refresh_token, self.settings)

        redis_key = self.settings.REFRESH_TOKEN_PROMPT.format(
            payload.user_id, payload.device_id
        )

        stored_jti = await self.cache.getdel(redis_key)

        if not stored_jti:
            raise UnauthorizedException("Refresh Token 已失效")

        if stored_jti != payload.jti:
            # 说明发生 refresh 重放攻击
            # 删除设备登录状态
            await self.cache.delete(redis_key)
            raise UnauthorizedException("检测到异常刷新行为")

        # 生成新 token（Rotation）
        new_access = create_access_token(payload.user_id, self.settings)
        new_refresh, new_jti = create_refresh_token(
            payload.user_id, payload.device_id, self.settings
        )

        # 存储新的 refresh
        await self.cache.setex(
            redis_key,
            self.settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
            new_jti,
        )

        return RefreshTokenResponse(
            access_token=new_access,
            refresh_token=new_refresh,
        )

    async def logout(
        self,
        logout_data: UserLogoutRequest,
        token_payload: TokenPayload,
    ) -> UserLogoutResponse:
        """
        当前设备登出逻辑：
        1. 拉黑 access token
        2. 删除对应 refresh token
        3. 删除设备
        """
        now = int(now_utc().timestamp())
        remaining_time = max(token_payload.exp - now, 0)

        # 拉黑 access token
        if remaining_time > 0:
            await self.cache.setex(
                self.settings.TOKEN_BLACKLIST_PROMPT.format(token_payload.jti),
                remaining_time,
                "1",
            )

        # 删除 refresh token
        payload = decode_refresh_token(logout_data.refresh_token, self.settings)
        await self.cache.delete(
            self.settings.REFRESH_TOKEN_PROMPT.format(
                payload.user_id, payload.device_id
            )
        )
        # 删除设备
        await self.cache.srem(
            self.settings.USER_DEVICES_SET_PROMPT.format(payload.user_id),
            payload.device_id,
        )
        return UserLogoutResponse(user_id=payload.user_id, device_id=payload.device_id)

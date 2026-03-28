from pydantic import BaseModel, Field

from app.common.base import BaseResponseSchema
from app.modules.users.schema import UserResponse


# 刷新Token相关请求和响应模型
class RefreshTokenRequest(BaseModel):
    """Refresh Token 刷新请求"""

    refresh_token: str


class RefreshTokenResponse(BaseModel):
    """Refresh Token 刷新响应"""

    access_token: str
    refresh_token: str


# 用户注册和登录相关请求和响应模型
class UserCreateRequest(BaseModel):
    """用户注册请求"""

    username: str = Field(..., description="用户名")
    password: str = Field(..., min_length=6, max_length=16, description="密码")
    device_id: str = Field(..., description="设备ID")


class UserLoginRequest(BaseModel):
    """用户登录请求"""

    username: str = Field(..., description="用户名")
    password: str = Field(..., min_length=6, max_length=16, description="密码")
    device_id: str = Field(..., description="设备ID")


class UserAuthedResponse(BaseResponseSchema):
    """登录/注册返回响应"""

    access_token: str
    refresh_token: str
    userInfo: UserResponse


class UserLogoutRequest(BaseModel):
    """用户登出请求"""

    refresh_token: str


class UserLogoutResponse(BaseResponseSchema):
    """用户登出响应"""

    user_id: int
    device_id: str

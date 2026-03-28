from enum import StrEnum

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class GenderEnum(StrEnum):
    """性别枚举（与数据库对应）"""

    male = "male"
    female = "female"
    unknown = "unknown"


class UserBase(BaseModel):
    """用户基础Schema"""

    username: str = Field(..., max_length=50, description="用户名")
    email: EmailStr | None = Field(None, max_length=100, description="邮箱")
    phone: str | None = Field(None, max_length=20, description="手机号")
    nickname: str | None = Field(None, max_length=50, description="昵称")
    avatar: str | None = Field(None, max_length=255, description="头像URL")
    gender: GenderEnum | None = Field(None, description="性别")
    bio: str | None = Field(None, max_length=500, description="个人简介")


class UserCreateRequest(UserBase):
    """用户创建请求"""

    password: str = Field(..., min_length=6, max_length=255, description="密码")

    model_config = ConfigDict(from_attributes=True)


class UserUpdateRequest(BaseModel):
    """用户更新请求"""

    email: EmailStr | None = Field(None, max_length=100, description="邮箱")
    phone: str | None = Field(None, max_length=20, description="手机号")
    nickname: str | None = Field(None, max_length=50, description="昵称")
    avatar: str | None = Field(None, max_length=255, description="头像URL")
    gender: GenderEnum | None = Field(None, description="性别")
    bio: str | None = Field(None, max_length=500, description="个人简介")

    model_config = ConfigDict(from_attributes=True)


class UserResponse(UserBase):
    """用户响应"""

    id: int = Field(..., description="用户ID")
    is_email_verified: bool = Field(..., description="邮箱是否已验证")
    is_phone_verified: bool = Field(..., description="手机号是否已验证")
    is_superuser: bool = Field(..., description="是否超级用户")
    is_active: bool = Field(..., description="是否激活")
    is_deleted: bool = Field(..., description="是否删除")

    model_config = {"from_attributes": True}


class UserPwdUpdateRequest(BaseModel):
    """用户密码更新请求"""

    old_password: str = Field(..., description="旧密码")
    new_password: str = Field(..., min_length=6, max_length=255, description="新密码")


class AvatarUpdateRequest(BaseModel):
    """头像更新请求"""

    avatar: str = Field(..., max_length=255, description="头像URL")


class AvatarUpdateResponse(BaseModel):
    """头像更新响应"""

    avatar: str = Field(..., description="头像URL")
    message: str = Field(default="头像更新成功", description="响应消息")

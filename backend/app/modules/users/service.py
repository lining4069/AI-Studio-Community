from typing import Any

from app.common.exceptions import DatabaseOperationException, ValidationException
from app.common.storage import AvatarFileStorage
from app.core.security import hash_password, verify_password
from app.modules.users.models import User
from app.modules.users.repository import UserRepository
from app.modules.users.schema import UserPwdUpdateRequest, UserUpdateRequest


class UserService:
    def __init__(
        self, repo: UserRepository, avatar_storage: AvatarFileStorage | None = None
    ):
        self.repo = repo
        self.avatar_storage = avatar_storage or AvatarFileStorage()

    def get_user_info(self, user: User) -> User:
        """获取用户信息"""
        return user

    async def update_user(
        self,
        user: User,
        update_data: UserUpdateRequest,
    ) -> User:
        """更新用户信息"""
        try:
            updated_user = await self.repo.update(user, update_data)
            return updated_user
        except Exception as e:
            raise DatabaseOperationException("用户", user.username, "更新") from e

    async def change_password(
        self,
        user: User,
        pwd_data: UserPwdUpdateRequest,
    ) -> None:
        """修改密码"""
        is_valid = verify_password(pwd_data.old_password, user.password)
        if not is_valid:
            raise ValidationException("输入旧密码错误,请修改后重试")

        hashed_pwd = hash_password(pwd_data.new_password)
        await self.repo.change_password(user, hashed_pwd)

    async def upload_avatar(self, user: User, file: Any) -> str:
        """上传头像"""
        # 删除旧头像文件
        if user.avatar and "/storage/avatar/" in user.avatar:
            await self.avatar_storage.delete(user.avatar)

        # 保存新头像
        avatar_url = await self.avatar_storage.save(file, user.id)

        # 更新用户头像URL
        await self.repo.update(
            user,
            UserUpdateRequest(
                avatar=avatar_url,
                email=None,
                phone=None,
                nickname=None,
                gender=None,
                bio=None,
            ),
        )

        return avatar_url

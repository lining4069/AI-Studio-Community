from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import User
from app.modules.users.schema import UserUpdateRequest


class UserRepository:
    """用户数据库操作"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # 查询
    async def get_by_id(self, user_id: int) -> User | None:
        """根据ID查询用户"""
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        """根据用户名查询用户"""
        stmt = select(User).where(User.username == username)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    # 更新
    async def update(
        self,
        user: User,
        update_data: UserUpdateRequest,
    ) -> User:
        """
        更新用户信息
        """
        data = update_data.model_dump(
            exclude_unset=True,
            exclude_none=True,
        )

        for field, value in data.items():
            setattr(user, field, value)

        await self.db.flush()

        return user

    # 修改密码
    async def change_password(
        self,
        user: User,
        hashed_password: str,
    ) -> None:
        user.password = hashed_password
        await self.db.flush()

    # 删除（软删除示例
    async def soft_delete(self, user: User) -> None:
        user.is_deleted = True
        await self.db.flush()

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.modules.auth.schema import UserCreateRequest
from app.modules.users.models import User


class AuthRepository:
    """认证相关的数据库操作"""

    def __init__(self, db: AsyncSession):
        self.db: AsyncSession = db

    async def create_user(self, user_data: UserCreateRequest) -> User:
        """注册用户"""
        hashed_pwd = hash_password(user_data.password)
        user = User(username=user_data.username, password=hashed_pwd)

        self.db.add(user)

        await self.db.commit()
        await self.db.refresh(user)

        return user

    async def get_user_by_username(self, username: str) -> User | None:
        """根据用户名查询用户"""
        result = await self.db.execute(
            select(User).where(
                User.username == username,
                User.is_active,
                ~User.is_deleted,
            )
        )
        return result.scalars().first()

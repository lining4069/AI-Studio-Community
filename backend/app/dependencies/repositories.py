from app.dependencies.infras import DBAsyncSession
from app.modules.auth.repository import AuthRepository
from app.modules.users.repository import UserRepository


# Auth 模块
def get_auth_repository(db: DBAsyncSession) -> AuthRepository:
    """
    Auth 模块 Repository 注入
    """
    return AuthRepository(db)


# 用户模块
def get_user_repository(db: DBAsyncSession) -> UserRepository:
    """
    用户模块 Repository 注入
    """
    return UserRepository(db)

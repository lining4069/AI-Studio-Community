from typing import Annotated

from fastapi import Depends

from app.common.storage import AvatarFileStorage
from app.dependencies.infras import AppSettings, CacheClient
from app.dependencies.repositories import get_auth_repository, get_user_repository
from app.dependencies.storage import get_avatar_storage
from app.modules.auth.repository import AuthRepository
from app.modules.auth.service import AuthService
from app.modules.users.repository import UserRepository
from app.modules.users.service import UserService


# Auth 模块
def get_auth_service(
    repo: Annotated[AuthRepository, Depends(get_auth_repository)],
    cache: CacheClient,
    settings: AppSettings,
) -> AuthService:
    """Auth 模块 Service 注入"""
    return AuthService(repo, cache, settings)


# 用户模块
def get_user_service(
    repo: Annotated[UserRepository, Depends(get_user_repository)],
    avatar_storage: Annotated[AvatarFileStorage, Depends(get_avatar_storage)],
) -> UserService:
    """用户模块 Service 注入"""
    return UserService(repo, avatar_storage)

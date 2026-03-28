from typing import Annotated

from fastapi import Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.storage import AvatarFileStorage, KnowledgeFileStorage
from app.core.settings import Settings, get_settings

from .cache import get_cache
from .database import get_db

# 系统设置依赖项类型
AppSettings = Annotated[Settings, Depends(get_settings)]

# 数据库会话依赖项类型
DBAsyncSession = Annotated[AsyncSession, Depends(get_db)]

# Redis缓存依赖项类型
CacheClient = Annotated[Redis, Depends(get_cache)]


# 注释外部可访问的名称
__all__ = [
    "AppSettings",
    "DBAsyncSession",
    "CacheClient",
]

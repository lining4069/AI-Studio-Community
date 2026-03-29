from fastapi import Depends

from app.common.storage import AvatarFileStorage, KnowledgeFileStorage
from app.core.settings import Settings, get_settings


def get_avatar_storage(settings: Settings = Depends(get_settings)) -> AvatarFileStorage:
    """获取头像存储实例"""
    return AvatarFileStorage(settings=settings)


def get_kb_file_storage(
    settings: Settings = Depends(get_settings),
) -> KnowledgeFileStorage:
    """获取知识库存储实例"""
    return KnowledgeFileStorage(settings=settings)

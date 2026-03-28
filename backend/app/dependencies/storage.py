from app.common.storage import AvatarFileStorage, KnowledgeFileStorage
from app.dependencies.infras import AppSettings


def get_avatar_storage(settings: AppSettings) -> AvatarFileStorage:
    """获取头像存储实例"""
    return AvatarFileStorage(settings=settings)


def get_kb_file_storage(settings: AppSettings) -> KnowledgeFileStorage:
    """获取知识库存储实例"""
    return KnowledgeFileStorage(settings=settings)

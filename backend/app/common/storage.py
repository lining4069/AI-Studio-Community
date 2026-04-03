"""
提供文件存储的抽象基类和具体实现：
- FileStorage: 抽象基类，定义存储接口
- AvatarFileStorage: 头像文件存储实现
- KnowledgeFileStorage: 知识库文档存储实现
"""

import asyncio
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from app.common.exceptions import ValidationException
from app.core.settings import Settings


class FileStorage(ABC):
    """文件存储抽象基类."""

    def __init__(
        self,
        relative_path: str,
        allowed_types: set[str],
        max_file_size: int,
        settings: Settings | None = None,
    ):
        """初始化文件存储.

        Args:
            relative_path: 相对于 BASE_DIR 的存储路径 (如 "storage/avatar")
            allowed_types: 允许的文件类型集合
            max_file_size: 最大文件大小 (字节)
            settings: 设置实例，如果为 None 则延迟获取
        """
        self.relative_path = relative_path
        self.allowed_types = allowed_types
        self.max_file_size = max_file_size
        self._settings = settings
        self._base_path: Path | None = None

    @property
    def settings(self) -> Settings:
        """延迟获取 settings."""
        if self._settings is None:
            from app.core.settings import get_settings

            self._settings = get_settings()
        return self._settings

    @property
    def base_path(self) -> Path:
        """获取基础路径（延迟初始化）."""
        if self._base_path is None:
            self._base_path = self.settings.BUSINESS_FILES_BASE_DIR / self.relative_path
        return self._base_path

    @abstractmethod
    async def save(self, file: Any, identifier: int | str, **kwargs) -> str:
        """保存文件并返回存储路径.

        Args:
            file: 上传的文件对象
            identifier: 标识符 (用户ID、知识库ID等)
            **kwargs: 额外的参数

        Returns:
            相对存储路径
        """
        pass

    @abstractmethod
    async def delete(self, relative_path: str) -> bool:
        """删除文件.

        Args:
            relative_path: 相对存储路径

        Returns:
            是否删除成功
        """
        pass

    async def _validate_file(self, file: Any) -> bytes:
        """验证文件大小和类型."""
        content = await file.read()
        file_size = len(content)

        if file_size > self.max_file_size:
            max_mb = self.max_file_size // (1024 * 1024)
            raise ValidationException(f"文件大小不能超过 {max_mb}MB")

        content_type = file.content_type
        if content_type not in self.allowed_types:
            allowed = ", ".join(sorted(self.allowed_types))
            raise ValidationException(f"不支持的文件类型，仅支持: {allowed}")

        return content

    def _get_extension(self, content_type: str) -> str:
        """从 content-type 获取文件扩展名."""
        extensions = self._get_extension_map()
        return extensions.get(content_type, "")

    @staticmethod
    def _write_file(file_path: Path, content: bytes) -> None:
        """同步文件写入操作（供 asyncio.to_thread 调用）."""
        with open(file_path, "wb") as f:
            f.write(content)

    @abstractmethod
    def _get_extension_map(self) -> dict[str, str]:
        """获取 content-type 到扩展名的映射表."""
        pass


# ============ 头像文件存储 ============


# 头像允许的图片类型
AVATAR_ALLOWED_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/gif",
    "image/webp",
}

# 头像最大文件大小: 5MB
AVATAR_MAX_SIZE = 5 * 1024 * 1024


class AvatarFileStorage(FileStorage):
    """头像文件存储实现.

    存储路径: {BUSINESS_FILES_BASE_DIR}/avatar/{user_id}/{uuid}.{ext}
    """

    def __init__(self, settings: Settings | None = None):
        super().__init__(
            relative_path="avatar",
            allowed_types=AVATAR_ALLOWED_TYPES,
            max_file_size=AVATAR_MAX_SIZE,
            settings=settings,
        )

    async def save(self, file: Any, identifier: int | str, **kwargs) -> str:
        """保存头像文件.

        Args:
            file: 上传的文件对象
            identifier: 用户ID

        Returns:
            相对存储路径，如 /storage/avatar/1/abc123.jpg
        """
        user_id = int(identifier)
        content = await self._validate_file(file)
        content_type = file.content_type

        # 生成唯一文件名
        file_ext = self._get_extension(content_type)
        filename = f"{uuid.uuid4().hex}{file_ext}"

        # 创建用户目录: {BUSINESS_FILES_BASE_DIR}/avatar/{user_id}/
        user_dir = self.base_path / str(user_id)
        user_dir.mkdir(parents=True, exist_ok=True)

        # 保存文件 (使用线程池避免阻塞)
        file_path = user_dir / filename
        await asyncio.to_thread(self._write_file, file_path, content)

        return f"/storage/avatar/{user_id}/{filename}"

    async def delete(self, relative_path: str) -> bool:
        """删除头像文件."""
        if not relative_path:
            return False

        # 转换为绝对路径并删除
        # relative_path 格式: /storage/avatar/{user_id}/{filename}
        # 需要去掉 /storage/avatar/ 前缀
        path_parts = relative_path.split("/storage/avatar/")
        if len(path_parts) > 1:
            file_path = self.base_path / path_parts[1]
        else:
            file_path = self.base_path / path_parts[0]

        if file_path.exists():
            file_path.unlink()
            return True
        return False

    def _get_extension_map(self) -> dict[str, str]:
        return {
            "image/jpeg": ".jpg",
            "image/jpg": ".jpg",
            "image/png": ".png",
            "image/gif": ".gif",
            "image/webp": ".webp",
        }


# ============ 知识库文档存储 ============


# 知识库允许的文档类型
KNOWLEDGE_ALLOWED_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/markdown",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/json",
    "text/json",
}

# 知识库文档最大文件大小: 50MB
KNOWLEDGE_MAX_SIZE = 50 * 1024 * 1024


class KnowledgeFileStorage(FileStorage):
    """知识库文档存储实现.

    存储路径: {BUSINESS_FILES_BASE_DIR}/knowledge/{user_id}/documents/{kb_id}/{uuid}.{ext}
    """

    # 扩展名到 content-type 的映射（用于后备验证）
    EXTENSION_CONTENT_TYPE_MAP: dict[str, str] = {
        ".md": "text/markdown",
        ".txt": "text/plain",
        ".pdf": "application/pdf",
        ".doc": "application/msword",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".xls": "application/vnd.ms-excel",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".json": "application/json",
    }

    def __init__(self, settings: Settings | None = None):
        super().__init__(
            relative_path="knowledge",
            allowed_types=KNOWLEDGE_ALLOWED_TYPES,
            max_file_size=KNOWLEDGE_MAX_SIZE,
            settings=settings,
        )

    async def _validate_file(self, file: Any) -> bytes:
        """验证文件大小和类型.

        支持两种验证方式：
        1. content-type 验证（主要方式）
        2. 文件扩展名验证（后备方式，用于 curl 等工具上传时 content-type 不正确的情况）
        """
        content = await file.read()
        file_size = len(content)

        if file_size > self.max_file_size:
            max_mb = self.max_file_size // (1024 * 1024)
            raise ValidationException(f"文件大小不能超过 {max_mb}MB")

        content_type = file.content_type

        # 如果 content-type 不在允许列表，尝试通过扩展名判断
        if content_type not in self.allowed_types:
            filename = file.filename or ""
            ext = Path(filename).suffix.lower()
            mapped_type = self.EXTENSION_CONTENT_TYPE_MAP.get(ext)

            if mapped_type and mapped_type in self.allowed_types:
                # 扩展名对应的类型在允许列表中，通过验证
                # 注意：不修改 file.content_type，保持原始值
                pass
            else:
                allowed = ", ".join(sorted(self.allowed_types))
                raise ValidationException(f"不支持的文件类型，仅支持: {allowed}")

        return content

    async def save(self, file: Any, identifier: int | str, **kwargs) -> str:
        """保存知识库文档.

        Args:
            file: 上传的文件对象
            identifier: 知识库ID (kb_id), can be int or string (UUID)
            **kwargs: 必须包含 user_id

        Returns:
            相对存储路径
        """
        # Handle both int and string identifiers (UUID support)
        kb_id_str = str(identifier)
        user_id = kwargs.get("user_id")
        if not user_id:
            raise ValidationException("缺少 user_id 参数")

        # Ensure user_id is converted to string for path
        user_id_str = str(user_id)

        content = await self._validate_file(file)
        content_type = file.content_type

        # 获取文件扩展名和修正后的文件类型
        original_ext = Path(file.filename or "").suffix.lower()
        file_ext = self._get_extension(content_type) or original_ext

        # 生成唯一文件名
        unique_name = f"{uuid.uuid4().hex}{file_ext}"

        # 创建知识库目录: {BUSINESS_FILES_BASE_DIR}/knowledge/{user_id}/documents/{kb_id}/
        kb_dir = self.base_path / user_id_str / "documents" / kb_id_str
        kb_dir.mkdir(parents=True, exist_ok=True)

        # 保存文件 (使用线程池避免阻塞)
        file_path = kb_dir / unique_name
        await asyncio.to_thread(self._write_file, file_path, content)

        # 返回相对路径: /storage/knowledge/{user_id}/documents/{kb_id}/{filename}
        return f"/storage/knowledge/{user_id_str}/documents/{kb_id_str}/{unique_name}"

    def get_file_type(self, content_type: str, filename: str) -> str:
        """获取修正后的文件类型.

        如果 content_type 是 application/octet-stream 或不在允许列表中，
        则根据文件扩展名推断正确的类型。

        Args:
            content_type: 文件的 content-type
            filename: 文件名

        Returns:
            正确的文件类型
        """
        if content_type in self.allowed_types:
            return content_type

        # 尝试通过扩展名获取正确的类型
        ext = Path(filename).suffix.lower()
        return self.EXTENSION_CONTENT_TYPE_MAP.get(ext, content_type)

    async def delete(self, relative_path: str) -> bool:
        """删除知识库文档.

        Args:
            relative_path: 相对路径，如 /storage/knowledge/{user_id}/documents/{kb_id}/{filename}

        Returns:
            是否删除成功

        Raises:
            ValidationException: 如果路径尝试遍历到存储目录之外
        """
        if not relative_path:
            return False

        # 转换为绝对路径
        # relative_path 格式: /storage/knowledge/{user_id}/documents/{kb_id}/{filename}
        # 需要去掉 /storage/ 前缀
        if relative_path.startswith("/storage/"):
            relative_path = relative_path[9:]  # 去掉 /storage/

        # 安全检查: 防止路径遍历攻击
        # 解析相对路径为绝对路径，并规范化（处理 .. 等）
        file_path = (self.base_path / relative_path).resolve()

        # 验证文件路径在 base_path 内，防止 ../etc/passwd 类型的攻击
        if not str(file_path).startswith(str(self.base_path.resolve())):
            raise ValidationException("无效的文件路径")

        if file_path.exists():
            file_path.unlink()
            return True
        return False

    def _get_extension_map(self) -> dict[str, str]:
        return {
            "application/pdf": ".pdf",
            "application/msword": ".doc",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
            "text/plain": ".txt",
            "text/markdown": ".md",
            "application/vnd.ms-excel": ".xls",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
        }


def get_vector_store_path(
    user_id: int, kb_id: str, settings: Settings | None = None
) -> str:
    """获取知识库向量存储路径.

    存储路径: {KNOWLEDGE_BASE_DIR}/{user_id}/vector/{kb_id}/

    Args:
        user_id: 用户ID
        kb_id: 知识库ID
        settings: 设置实例

    Returns:
        向量存储的持久化目录路径
    """
    if settings is None:
        from app.core.settings import get_settings

        settings = get_settings()

    vector_dir = (
        settings.BUSINESS_FILES_BASE_DIR
        / "knowledge"
        / str(user_id)
        / "vector"
        / str(kb_id)
    )
    vector_dir.mkdir(parents=True, exist_ok=True)
    return str(vector_dir)

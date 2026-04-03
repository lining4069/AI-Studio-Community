"""RAG Store 抽象基类和核心数据结构"""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class DocumentUnit(BaseModel):
    """RAG 模块/服务中循环流通的数据结构"""

    document_id: str  # 外部生成的 UUID
    kb_id: str
    file_id: str
    content: str  # 原始文本
    metadata: dict = Field(default_factory=dict)  # 额外元数据


class DenseStore(ABC):
    """稠密向量存储抽象基类"""

    @abstractmethod
    async def add_documents(self, docs: list[DocumentUnit]) -> None:
        """添加文档到稠密存储"""
        pass

    @abstractmethod
    async def retrieve(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[tuple[DocumentUnit, float]]:
        """
        检索匹配的文档

        Returns:
            list of (DocumentUnit, score)
        """
        pass

    @abstractmethod
    async def delete_by_document_ids(self, document_ids: list[str]) -> int:
        """根据 document_id 删除文档"""
        pass

    @abstractmethod
    async def delete_by_file_id(self, file_id: str) -> int:
        """根据 file_id 删除文档"""
        pass


class SparseStore(ABC):
    """稀疏存储抽象基类（BM25 关键词检索）"""

    @abstractmethod
    async def add_documents(self, docs: list[DocumentUnit]) -> None:
        """添加文档到稀疏存储（写入时完成 jieba 分词）"""
        pass

    @abstractmethod
    async def retrieve(
        self,
        query: str,
        top_k: int = 10,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[tuple[DocumentUnit, float]]:
        """
        检索匹配的文档

        Returns:
            list of (DocumentUnit, score)
        """
        pass

    @abstractmethod
    async def delete_by_document_ids(self, document_ids: list[str]) -> int:
        """根据 document_id 删除文档"""
        pass

    @abstractmethod
    async def delete_by_file_id(self, file_id: str) -> int:
        """根据 file_id 删除文档"""
        pass

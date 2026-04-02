"""Text Splitter — 支持 recursive 和 markdown 两种分块模式"""

from langchain_core.documents import Document
from langchain_text_splitters import (
    MarkdownTextSplitter,
    RecursiveCharacterTextSplitter,
)


class TextSplitter:
    """
    文本分块器

    支持模式：
    - "recursive": RecursiveCharacterTextSplitter，按字符递归分割
    - "markdown": MarkdownTextSplitter，按 Markdown 标题结构分割
    """

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        mode: str = "recursive",
    ) -> None:
        """
        初始化 TextSplitter

        Args:
            chunk_size: 分块大小（字符数）
            chunk_overlap: 分块重叠大小
            mode: 分块模式，"recursive" 或 "markdown"
        """
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if chunk_overlap < 0:
            raise ValueError("chunk_overlap must be non-negative")
        if mode not in ("recursive", "markdown"):
            raise ValueError("mode must be 'recursive' or 'markdown'")

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.mode = mode

    def _get_splitter(self) -> RecursiveCharacterTextSplitter | MarkdownTextSplitter:
        """获取对应的分割器实例"""
        if self.mode == "markdown":
            return MarkdownTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
            )
        else:
            return RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
            )

    def split_documents(self, documents: list[Document]) -> list[Document]:
        """
        分割文档列表

        Args:
            documents: LangChain Document 列表

        Returns:
            分割后的 Document 列表
        """
        splitter = self._get_splitter()
        return splitter.split_documents(documents)

    def split_text(self, text: str) -> list[str]:
        """
        分割单个文本

        Args:
            text: 要分割的文本

        Returns:
            分割后的文本列表
        """
        splitter = self._get_splitter()
        return splitter.split_text(text)

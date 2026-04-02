"""Document Loader — 支持多种文件类型加载"""

from pathlib import Path
from typing import Any

from langchain_community.document_loaders import (
    CSVLoader,
    Docx2txtLoader,
    JSONLoader,
    PyPDFLoader,
    TextLoader,
)
from langchain_core.documents import Document


class DocumentLoader:
    """
    文档加载器，支持多种文件类型

    支持类型：txt, md, pdf, docx, csv, jsonl
    使用注册表模式，按文件扩展名路由到对应加载器
    """

    _LOADER_REGISTRY: dict[str, Any] = {
        ".txt": TextLoader,
        ".md": TextLoader,
        ".pdf": PyPDFLoader,
        ".docx": Docx2txtLoader,
        ".csv": CSVLoader,
        ".jsonl": JSONLoader,
    }

    def load(
        self, file_path: str | Path, encoding: str = "utf-8"
    ) -> list[Document]:
        """
        加载文件，返回 LangChain Document 列表

        Args:
            file_path: 文件路径
            encoding: 编码格式

        Returns:
            LangChain Document 列表
        """
        path = Path(file_path)
        ext = path.suffix.lower()

        loader_cls = self._LOADER_REGISTRY.get(ext)
        if not loader_cls:
            raise ValueError(f"Unsupported file type: {ext}")

        # CSVLoader 和 JSONLLoader 需要特殊处理
        if ext == ".csv":
            loader = CSVLoader(file_path=str(path), encoding=encoding)
        elif ext == ".jsonl":
            loader = JSONLoader(file_path=str(path), jq_schema=".", json_lines=True)
        else:
            loader = loader_cls(str(path), encoding=encoding)

        return loader.load()

    def load_with_metadata(
        self,
        file_path: str | Path,
        metadata: dict,
        encoding: str = "utf-8",
    ) -> list[Document]:
        """
        加载文件并合并元数据

        Args:
            file_path: 文件路径
            metadata: 要合并的元数据
            encoding: 编码格式

        Returns:
            包含合并元数据的 LangChain Document 列表
        """
        docs = self.load(file_path, encoding)
        for doc in docs:
            doc.metadata.update(metadata)
        return docs
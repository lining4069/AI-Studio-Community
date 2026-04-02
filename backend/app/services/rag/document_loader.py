"""Document Loader — 支持多种文件类型加载"""

from pathlib import Path

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
    使用 loader 工厂模式，按文件扩展名路由到对应加载器
    """

    _LOADER_FACTORIES: dict[str, callable] = {
        ".txt": lambda path, enc: TextLoader(path, encoding=enc),
        ".md": lambda path, enc: TextLoader(path, encoding=enc),
        ".pdf": lambda path, enc: PyPDFLoader(path),
        ".docx": lambda path, enc: Docx2txtLoader(path),
        ".csv": lambda path, enc: CSVLoader(path, encoding=enc),
        ".jsonl": lambda path, enc: JSONLoader(path, jq_schema=".", json_lines=True),
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

        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        ext = path.suffix.lower()
        factory = self._LOADER_FACTORIES.get(ext)
        if not factory:
            raise ValueError(f"Unsupported file type: {ext}")

        loader = factory(str(path), encoding)
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
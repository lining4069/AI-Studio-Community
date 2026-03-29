"""
Text splitting utilities for document processing.

Provides recursive character splitting with overlap for RAG ingestion.
"""

import asyncio
import re
from collections.abc import Iterator
from pathlib import Path


class TextSplitter:
    """
    Recursive text splitter that splits documents into overlapping chunks.

    Supports multiple splitting strategies and preserves metadata.
    """

    DEFAULT_SEPARATORS = ["\n\n", "\n", "。", "！", "？", "，", "、", " ", ""]

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        separators: list[str] | None = None,
        keep_separator: bool = True,
    ):
        """
        Initialize text splitter.

        Args:
            chunk_size: Target size for each chunk (in characters)
            chunk_overlap: Overlap between chunks
            separators: List of separator strings (in priority order)
            keep_separator: Whether to keep separators in chunks
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or self.DEFAULT_SEPARATORS
        self.keep_separator = keep_separator

    def split_text(self, text: str) -> list[str]:
        """
        Split text into chunks.

        Args:
            text: Input text

        Returns:
            List of chunk strings
        """
        if not text:
            return []

        return list(self._split_text_recursive(text, 0))

    def _split_text_recursive(self, text: str, separator_index: int) -> Iterator[str]:
        """
        Recursively split text using separators.

        Args:
            text: Text to split
            separator_index: Index into separators list

        Yields:
            Chunk strings
        """
        separator = (
            self.separators[separator_index]
            if separator_index < len(self.separators)
            else ""
        )

        if separator == "":
            # Final fallback: split by character count
            for i in range(0, len(text), self.chunk_size - self.chunk_overlap):
                chunk = text[i : i + self.chunk_size]
                if chunk:
                    yield chunk
            return

        # Try to split by current separator
        splits = text.split(separator) if separator else [text]

        current_chunk = ""
        for _i, split in enumerate(splits):
            candidate = (
                split if not current_chunk else current_chunk + separator + split
            )

            if len(candidate) <= self.chunk_size:
                current_chunk = candidate
            else:
                # Current chunk is full
                if current_chunk:
                    yield current_chunk
                    # Start new chunk with overlap
                    if (
                        self.chunk_overlap > 0
                        and len(current_chunk) > self.chunk_overlap
                    ):
                        current_chunk = current_chunk[-self.chunk_overlap :]
                    else:
                        current_chunk = ""
                else:
                    # Single split is too big, recurse with smaller separator
                    if split:
                        yield from self._split_text_recursive(
                            split, separator_index + 1
                        )

        # Don't forget the last chunk
        if current_chunk:
            yield current_chunk

    def split_texts_with_metadata(
        self, texts: list[str], metadatas: list[dict] | None = None
    ) -> list[dict]:
        """
        Split texts and attach metadata to each chunk.

        Args:
            texts: List of texts
            metadatas: Optional list of metadata dicts (one per text)

        Returns:
            List of dicts with keys: content, metadata, chunk_index
        """
        if metadatas is None:
            metadatas = [{} for _ in texts]

        chunks = []
        for text, metadata in zip(texts, metadatas, strict=True):
            text_chunks = self.split_text(text)
            for i, chunk in enumerate(text_chunks):
                chunks.append(
                    {
                        "content": chunk,
                        "metadata": {**metadata, "chunk_index": i},
                        "chunk_index": len(chunks),
                    }
                )

        return chunks


class DocumentProcessor:
    """
    Processes various document formats into chunks.

    Supports: TXT, PDF, DOCX, MARKDOWN, CSV, JSONL
    """

    def __init__(
        self,
        splitter: TextSplitter | None = None,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
    ):
        self.splitter = splitter or TextSplitter(
            chunk_size=chunk_size, chunk_overlap=chunk_overlap
        )

    @staticmethod
    def _read_text_file(file_path: str) -> str:
        """Read text file in a blocking manner (to be run in thread pool)"""
        with open(file_path, encoding="utf-8", errors="ignore") as f:
            return f.read()

    async def process_file(
        self, file_path: str, metadata: dict | None = None
    ) -> list[dict]:
        """
        Process a file and return chunks.

        Args:
            file_path: Path to the file
            metadata: Additional metadata to attach to chunks

        Returns:
            List of chunk dicts with content, metadata, chunk_index
        """
        path = Path(file_path)
        suffix = path.suffix.lower()

        metadata = metadata or {}
        metadata["file_name"] = path.name
        metadata["file_path"] = str(file_path)

        if suffix == ".txt" or suffix == ".text":
            return await self._process_txt(file_path, metadata)
        elif suffix == ".md" or suffix == ".markdown":
            return await self._process_markdown(file_path, metadata)
        elif suffix == ".pdf":
            return await self._process_pdf(file_path, metadata)
        elif suffix in [".docx", ".doc"]:
            return await self._process_docx(file_path, metadata)
        elif suffix == ".csv":
            return await self._process_csv(file_path, metadata)
        elif suffix == ".jsonl":
            return await self._process_jsonl(file_path, metadata)
        else:
            # Default: treat as plain text
            return await self._process_txt(file_path, metadata)

    async def _process_txt(self, file_path: str, metadata: dict) -> list[dict]:
        """Process plain text file"""
        text = await asyncio.to_thread(self._read_text_file, file_path)
        chunks = self.splitter.split_texts_with_metadata([text], [metadata])
        return chunks

    async def _process_markdown(self, file_path: str, metadata: dict) -> list[dict]:
        """Process markdown file, splitting by headers when possible"""
        text = await asyncio.to_thread(self._read_text_file, file_path)

        # Split by headers for better semantic chunking
        header_splits = re.split(r"(?=\n#{1,6}\s)", text)

        processed_chunks = []
        for split in header_splits:
            if split.strip():
                # Further split each section
                section_chunks = self.splitter.split_texts_with_metadata(
                    [split], [{**metadata, "section": "header"}]
                )
                processed_chunks.extend(section_chunks)

        if not processed_chunks:
            # Fallback to plain text splitting
            processed_chunks = self.splitter.split_texts_with_metadata(
                [text], [metadata]
            )

        return processed_chunks

    async def _process_pdf(self, file_path: str, metadata: dict) -> list[dict]:
        """Process PDF file using pdfplumber or pypdf"""
        try:
            import pdfplumber

            texts = []
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        texts.append(page_text)

            all_chunks = self.splitter.split_texts_with_metadata(
                texts,
                [{**metadata, "source": f"page_{i + 1}"} for i in range(len(texts))],
            )
            return all_chunks
        except ImportError:
            # Fallback to plain text
            return await self._process_txt(file_path, metadata)

    async def _process_docx(self, file_path: str, metadata: dict) -> list[dict]:
        """Process DOCX file using python-docx"""
        try:
            from docx import Document

            texts = []
            doc = Document(file_path)
            for para in doc.paragraphs:
                if para.text.strip():
                    texts.append(para.text)

            all_chunks = self.splitter.split_texts_with_metadata(
                texts, [metadata for _ in texts]
            )
            return all_chunks
        except ImportError:
            return await self._process_txt(file_path, metadata)

    async def _process_csv(self, file_path: str, metadata: dict) -> list[dict]:
        """Process CSV file, treating each row as a text unit"""
        try:
            import csv

            def _read_csv():
                rows = []
                with open(file_path, encoding="utf-8", errors="ignore") as f:
                    reader = csv.reader(f)
                    for row in reader:
                        rows.append(", ".join(filter(None, row)))
                return rows

            rows = await asyncio.to_thread(_read_csv)

            all_chunks = self.splitter.split_texts_with_metadata(
                rows, [{**metadata, "source": f"row_{i + 1}"} for i in range(len(rows))]
            )
            return all_chunks
        except Exception:
            return await self._process_txt(file_path, metadata)

    async def _process_jsonl(self, file_path: str, metadata: dict) -> list[dict]:
        """Process JSONL file, treating each line as a text unit"""
        import json

        def _read_jsonl():
            texts = []
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if line.strip():
                        try:
                            obj = json.loads(line)
                            text = json.dumps(obj, ensure_ascii=False)
                            texts.append(text)
                        except json.JSONDecodeError:
                            texts.append(line.strip())
            return texts

        texts = await asyncio.to_thread(_read_jsonl)

        all_chunks = self.splitter.split_texts_with_metadata(
            texts, [{**metadata, "source": f"line_{i + 1}"} for i in range(len(texts))]
        )
        return all_chunks

"""
Knowledge Base repository for database operations.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.knowledge_base.models import KbDocument, KbFile


class KbDocumentRepository:
    """Repository for KbDocument database operations"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, user_id: int, data, collection_name: str) -> KbDocument:
        """Create a new Knowledge Base document"""
        model = KbDocument(
            user_id=user_id,
            name=data.name,
            description=data.description,
            embedding_model_id=data.embedding_model_id,
            rerank_model_id=data.rerank_model_id,
            chunk_size=data.chunk_size,
            chunk_overlap=data.chunk_overlap,
            top_k=data.top_k,
            similarity_threshold=data.similarity_threshold,
            vector_weight=data.vector_weight,
            enable_rerank=data.enable_rerank,
            rerank_top_k=data.rerank_top_k,
            collection_name=collection_name,
        )
        self.db.add(model)
        await self.db.flush()
        await self.db.refresh(model)
        return model

    async def get_by_id(self, kb_id: str, user_id: int) -> KbDocument | None:
        """Get Knowledge Base by ID"""
        stmt = select(KbDocument).where(
            KbDocument.id == kb_id, KbDocument.user_id == user_id
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_name(self, user_id: int, name: str) -> KbDocument | None:
        """Get Knowledge Base by name for a user"""
        stmt = select(KbDocument).where(
            KbDocument.user_id == user_id, KbDocument.name == name
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_user(
        self, user_id: int, page: int = 1, page_size: int = 20
    ) -> tuple[list[KbDocument], int]:
        """List Knowledge Bases with pagination"""
        count_stmt = (
            select(func.count())
            .select_from(KbDocument)
            .where(KbDocument.user_id == user_id)
        )
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar_one()

        offset = (page - 1) * page_size
        stmt = (
            select(KbDocument)
            .where(KbDocument.user_id == user_id)
            .order_by(KbDocument.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        items = list(result.scalars().all())

        return items, total

    async def update(self, kb: KbDocument, data) -> KbDocument:
        """Update a Knowledge Base"""
        update_dict = data.model_dump(exclude_unset=True)

        for field, value in update_dict.items():
            setattr(kb, field, value)

        await self.db.flush()
        await self.db.refresh(kb)
        return kb

    async def delete(self, kb: KbDocument) -> None:
        """Delete a Knowledge Base"""
        await self.db.delete(kb)
        await self.db.flush()


class KbFileRepository:
    """Repository for KbFile database operations"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, user_id: int, kb_id: str, data, file_md5: str) -> KbFile:
        """Create a new Knowledge Base file record"""
        model = KbFile(
            user_id=user_id,
            kb_id=kb_id,
            file_name=data.file_name,
            file_path=data.file_path,
            file_size=data.file_size,
            file_type=data.file_type,
            file_md5=file_md5,
            status="pending",
            file_metadata={},
        )
        self.db.add(model)
        await self.db.flush()
        await self.db.refresh(model)
        return model

    async def get_by_id(self, file_id: str, user_id: int) -> KbFile | None:
        """Get file by ID"""
        stmt = select(KbFile).where(KbFile.id == file_id, KbFile.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_md5(self, kb_id: str, file_md5: str) -> KbFile | None:
        """Get file by MD5 within a KB (for deduplication)"""
        stmt = select(KbFile).where(KbFile.kb_id == kb_id, KbFile.file_md5 == file_md5)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_kb(
        self,
        kb_id: str,
        user_id: int,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
    ) -> tuple[list[KbFile], int]:
        """List files in a Knowledge Base"""
        base_filter = [KbFile.kb_id == kb_id, KbFile.user_id == user_id]
        if status:
            base_filter.append(KbFile.status == status)

        count_stmt = select(func.count()).select_from(KbFile).where(*base_filter)
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar_one()

        offset = (page - 1) * page_size
        stmt = (
            select(KbFile)
            .where(*base_filter)
            .order_by(KbFile.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        items = list(result.scalars().all())

        return items, total

    async def update(self, file: KbFile, **kwargs) -> KbFile:
        """Update a file record"""
        for key, value in kwargs.items():
            setattr(file, key, value)
        await self.db.flush()
        await self.db.refresh(file)
        return file

    async def delete(self, file: KbFile) -> None:
        """Delete a file record"""
        await self.db.delete(file)
        await self.db.flush()


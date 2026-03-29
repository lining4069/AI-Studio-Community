"""
Embedding Model repository for database operations.
"""

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.embedding_model.models import EmbeddingModel
from app.modules.embedding_model.schema import (
    EmbeddingModelCreate,
    EmbeddingModelUpdate,
)


class EmbeddingModelRepository:
    """Repository for Embedding Model database operations"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        user_id: int,
        data: EmbeddingModelCreate,
        encrypted_api_key: str | None = None,
    ) -> EmbeddingModel:
        """Create a new Embedding model"""
        model = EmbeddingModel(
            user_id=user_id,
            name=data.name,
            type=data.type.value,
            model_name=data.model_name,
            endpoint=data.endpoint,
            api_key=None,
            encrypted_api_key=encrypted_api_key,
            local_model_path=data.local_model_path,
            dimension=data.dimension,
            batch_size=data.batch_size,
            is_enabled=data.is_enabled,
            is_default=data.is_default,
            description=data.description,
        )
        self.db.add(model)
        await self.db.flush()
        await self.db.refresh(model)
        return model

    async def get_by_id(self, model_id: str, user_id: int) -> EmbeddingModel | None:
        """Get Embedding model by ID"""
        stmt = select(EmbeddingModel).where(
            EmbeddingModel.id == model_id, EmbeddingModel.user_id == user_id
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_name(self, user_id: int, name: str) -> EmbeddingModel | None:
        """Get Embedding model by name for a user"""
        stmt = select(EmbeddingModel).where(
            EmbeddingModel.user_id == user_id, EmbeddingModel.name == name
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_user(
        self, user_id: int, page: int = 1, page_size: int = 20
    ) -> tuple[list[EmbeddingModel], int]:
        """List Embedding models with pagination"""
        # Count total
        count_stmt = (
            select(func.count())
            .select_from(EmbeddingModel)
            .where(EmbeddingModel.user_id == user_id)
        )
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar_one()

        # Get paginated results
        offset = (page - 1) * page_size
        stmt = (
            select(EmbeddingModel)
            .where(EmbeddingModel.user_id == user_id)
            .order_by(EmbeddingModel.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        items = list(result.scalars().all())

        return items, total

    async def update(
        self,
        model: EmbeddingModel,
        data: EmbeddingModelUpdate,
        encrypted_api_key: str | None = None,
    ) -> EmbeddingModel:
        """Update an Embedding model"""
        update_data = data.model_dump(exclude_unset=True, exclude_none=True)

        # Handle type conversion for enum
        if "type" in update_data and update_data["type"]:
            update_data["type"] = update_data["type"].value

        for field, value in update_data.items():
            setattr(model, field, value)

        if encrypted_api_key is not None:
            model.encrypted_api_key = encrypted_api_key

        await self.db.flush()
        await self.db.refresh(model)
        return model

    async def delete(self, model: EmbeddingModel) -> None:
        """Delete an Embedding model"""
        await self.db.delete(model)
        await self.db.flush()

    async def get_default(self, user_id: int) -> EmbeddingModel | None:
        """Get the default Embedding model for a user"""
        stmt = select(EmbeddingModel).where(
            EmbeddingModel.user_id == user_id,
            EmbeddingModel.is_default,
            EmbeddingModel.is_enabled,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def clear_default_flags(self, user_id: int) -> None:
        """Clear all default flags for a user's models"""
        stmt = (
            update(EmbeddingModel)
            .where(EmbeddingModel.user_id == user_id, EmbeddingModel.is_default)
            .values(is_default=False)
        )
        await self.db.execute(stmt)
        await self.db.flush()

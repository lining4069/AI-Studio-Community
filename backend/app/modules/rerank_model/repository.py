"""
Rerank Model repository for database operations.
"""

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.rerank_model.models import RerankModel
from app.modules.rerank_model.schema import RerankModelCreate, RerankModelUpdate


class RerankModelRepository:
    """Repository for Rerank Model database operations"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, user_id: int, data: RerankModelCreate) -> RerankModel:
        """Create a new Rerank model"""
        model = RerankModel(
            user_id=user_id,
            name=data.name,
            type=data.type.value,
            model_name=data.model_name,
            base_url=data.base_url,
            api_key=None,
            encrypted_api_key=data.encrypted_api_key,
            top_n=data.top_n,
            is_enabled=data.is_enabled,
            is_default=data.is_default,
            description=data.description,
        )
        self.db.add(model)
        await self.db.flush()
        await self.db.refresh(model)
        return model

    async def get_by_id(self, model_id: str, user_id: int) -> RerankModel | None:
        """Get Rerank model by ID"""
        stmt = select(RerankModel).where(
            RerankModel.id == model_id, RerankModel.user_id == user_id
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_name(self, user_id: int, name: str) -> RerankModel | None:
        """Get Rerank model by name for a user"""
        stmt = select(RerankModel).where(
            RerankModel.user_id == user_id, RerankModel.name == name
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_user(
        self, user_id: int, page: int = 1, page_size: int = 20
    ) -> tuple[list[RerankModel], int]:
        """List Rerank models with pagination"""
        # Count total
        count_stmt = (
            select(func.count())
            .select_from(RerankModel)
            .where(RerankModel.user_id == user_id)
        )
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar_one()

        # Get paginated results
        offset = (page - 1) * page_size
        stmt = (
            select(RerankModel)
            .where(RerankModel.user_id == user_id)
            .order_by(RerankModel.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        items = list(result.scalars().all())

        return items, total

    async def update(self, model: RerankModel, data: RerankModelUpdate) -> RerankModel:
        """Update a Rerank model"""
        update_data = data.model_dump(exclude_unset=True, exclude_none=True)

        # Handle type conversion for enum
        if "type" in update_data and update_data["type"]:
            update_data["type"] = update_data["type"].value

        for field, value in update_data.items():
            setattr(model, field, value)

        await self.db.flush()
        await self.db.refresh(model)
        return model

    async def delete(self, model: RerankModel) -> None:
        """Delete a Rerank model"""
        await self.db.delete(model)
        await self.db.flush()

    async def get_default(self, user_id: int) -> RerankModel | None:
        """Get the default Rerank model for a user"""
        stmt = select(RerankModel).where(
            RerankModel.user_id == user_id,
            RerankModel.is_default == True,
            RerankModel.is_enabled == True,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def clear_default_flags(self, user_id: int) -> None:
        """Clear all default flags for a user's models"""
        stmt = (
            update(RerankModel)
            .where(RerankModel.user_id == user_id, RerankModel.is_default == True)
            .values(is_default=False)
        )
        await self.db.execute(stmt)
        await self.db.flush()

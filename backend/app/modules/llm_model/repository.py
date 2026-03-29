"""
LLM Model repository for database operations.
"""

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.llm_model.models import LlmModel
from app.modules.llm_model.schema import LlmModelCreate, LlmModelUpdate


class LlmModelRepository:
    """Repository for LLM Model database operations"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        user_id: int,
        data: LlmModelCreate,
        encrypted_api_key: str | None = None,
    ) -> LlmModel:
        """Create a new LLM model"""
        model = LlmModel(
            user_id=user_id,
            name=data.name,
            provider=data.provider,
            model_name=data.model_name,
            base_url=data.base_url,
            api_key=None,
            encrypted_api_key=encrypted_api_key,
            temperature=data.temperature,
            max_tokens=data.max_tokens,
            context_window=data.context_window,
            support_vision=data.support_vision,
            support_function_calling=data.support_function_calling,
            is_enabled=data.is_enabled,
            is_default=data.is_default,
            description=data.description,
        )
        self.db.add(model)
        await self.db.flush()
        await self.db.refresh(model)
        return model

    async def get_by_id(self, model_id: str, user_id: int) -> LlmModel | None:
        """Get LLM model by ID"""
        stmt = select(LlmModel).where(
            LlmModel.id == model_id, LlmModel.user_id == user_id
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_name(self, user_id: int, name: str) -> LlmModel | None:
        """Get LLM model by name for a user"""
        stmt = select(LlmModel).where(
            LlmModel.user_id == user_id, LlmModel.name == name
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_user(
        self, user_id: int, page: int = 1, page_size: int = 20
    ) -> tuple[list[LlmModel], int]:
        """List LLM models with pagination"""
        # Count total
        count_stmt = (
            select(func.count())
            .select_from(LlmModel)
            .where(LlmModel.user_id == user_id)
        )
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar_one()

        # Get paginated results
        offset = (page - 1) * page_size
        stmt = (
            select(LlmModel)
            .where(LlmModel.user_id == user_id)
            .order_by(LlmModel.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        items = list(result.scalars().all())

        return items, total

    async def update(
        self,
        model: LlmModel,
        data: LlmModelUpdate,
        encrypted_api_key: str | None = None,
    ) -> LlmModel:
        """Update an LLM model"""
        update_data = data.model_dump(exclude_unset=True, exclude_none=True)

        for field, value in update_data.items():
            setattr(model, field, value)

        if encrypted_api_key is not None:
            model.encrypted_api_key = encrypted_api_key

        await self.db.flush()
        await self.db.refresh(model)
        return model

    async def delete(self, model: LlmModel) -> None:
        """Delete an LLM model"""
        await self.db.delete(model)
        await self.db.flush()

    async def get_default(self, user_id: int) -> LlmModel | None:
        """Get the default LLM model for a user"""
        stmt = select(LlmModel).where(
            LlmModel.user_id == user_id,
            LlmModel.is_default,
            LlmModel.is_enabled,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def clear_default_flags(self, user_id: int) -> None:
        """Clear all default flags for a user's models"""
        stmt = (
            update(LlmModel)
            .where(LlmModel.user_id == user_id, LlmModel.is_default)
            .values(is_default=False)
        )
        await self.db.execute(stmt)
        await self.db.flush()

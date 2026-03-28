"""
Rerank Model service for business logic.
"""
from typing import List, Optional, Tuple

from app.common.exceptions import NotFoundException, ValidationException
from app.modules.rerank_model.models import RerankModel
from app.modules.rerank_model.repository import RerankModelRepository
from app.modules.rerank_model.schema import RerankModelCreate, RerankModelUpdate
from app.utils.encrypt_utils import encrypt_api_key


class RerankModelService:
    """Business logic for Rerank Model"""

    def __init__(self, repo: RerankModelRepository):
        self.repo = repo

    async def create_model(
        self, user_id: int, data: RerankModelCreate
    ) -> RerankModel:
        """Create a new Rerank model"""
        # Check if name already exists for this user
        existing = await self.repo.get_by_name(user_id, data.name)
        if existing:
            raise ValidationException(f"Rerank model with name '{data.name}' already exists")

        # If setting as default, clear other defaults first
        if data.is_default:
            await self.repo.clear_default_flags(user_id)

        # Encrypt API key if provided
        encrypted_key = None
        if data.api_key:
            encrypted_key = encrypt_api_key(data.api_key)
            data.encrypted_api_key = encrypted_key

        model = await self.repo.create(user_id, data)
        return model

    async def get_model(self, model_id: str, user_id: int) -> RerankModel:
        """Get a Rerank model by ID"""
        model = await self.repo.get_by_id(model_id, user_id)
        if not model:
            raise NotFoundException("Rerank Model", model_id)
        return model

    async def list_models(
        self, user_id: int, page: int = 1, page_size: int = 20
    ) -> Tuple[List[RerankModel], int]:
        """List Rerank models with pagination"""
        return await self.repo.list_by_user(user_id, page, page_size)

    async def update_model(
        self, model_id: str, user_id: int, data: RerankModelUpdate
    ) -> RerankModel:
        """Update a Rerank model"""
        model = await self.get_model(model_id, user_id)

        # If setting as default, clear other defaults first
        if data.is_default:
            await self.repo.clear_default_flags(user_id)

        # If new API key provided, re-encrypt it
        if data.api_key:
            data.encrypted_api_key = encrypt_api_key(data.api_key)

        updated = await self.repo.update(model, data)
        return updated

    async def delete_model(self, model_id: str, user_id: int) -> None:
        """Delete a Rerank model"""
        model = await self.get_model(model_id, user_id)
        await self.repo.delete(model)

    async def get_default_model(self, user_id: int) -> Optional[RerankModel]:
        """Get the default Rerank model"""
        return await self.repo.get_default(user_id)

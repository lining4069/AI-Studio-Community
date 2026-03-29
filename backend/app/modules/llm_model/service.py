"""
LLM Model service for business logic.
"""

from app.common.exceptions import NotFoundException, ValidationException
from app.modules.llm_model.models import LlmModel
from app.modules.llm_model.repository import LlmModelRepository
from app.modules.llm_model.schema import (
    LlmModelCreate,
    LlmModelUpdate,
)
from app.utils.encrypt_utils import encrypt_api_key


class LlmModelService:
    """Business logic for LLM Model"""

    def __init__(self, repo: LlmModelRepository):
        self.repo = repo

    async def create_model(self, user_id: int, data: LlmModelCreate) -> LlmModel:
        """Create a new LLM model"""
        # Check if name already exists for this user
        existing = await self.repo.get_by_name(user_id, data.name)
        if existing:
            raise ValidationException(
                f"LLM model with name '{data.name}' already exists"
            )

        # If setting as default, clear other defaults first
        if data.is_default:
            await self.repo.clear_default_flags(user_id)

        # Encrypt API key if provided
        encrypted_key = None
        if data.api_key:
            encrypted_key = encrypt_api_key(data.api_key)

        # Create with encrypted key
        data.encrypted_api_key = encrypted_key

        model = await self.repo.create(user_id, data)
        return model

    async def get_model(self, model_id: str, user_id: int) -> LlmModel:
        """Get a LLM model by ID"""
        model = await self.repo.get_by_id(model_id, user_id)
        if not model:
            raise NotFoundException("LLM Model", model_id)
        return model

    async def list_models(
        self, user_id: int, page: int = 1, page_size: int = 20
    ) -> tuple[list[LlmModel], int]:
        """List LLM models with pagination"""
        return await self.repo.list_by_user(user_id, page, page_size)

    async def update_model(
        self, model_id: str, user_id: int, data: LlmModelUpdate
    ) -> LlmModel:
        """Update a LLM model"""
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
        """Delete a LLM model"""
        model = await self.get_model(model_id, user_id)
        await self.repo.delete(model)

    async def get_default_model(self, user_id: int) -> LlmModel | None:
        """Get the default LLM model"""
        return await self.repo.get_default(user_id)

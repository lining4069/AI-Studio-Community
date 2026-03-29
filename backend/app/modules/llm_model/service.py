"""
LLM Model service for business logic.
"""

from app.common.exceptions import NotFoundException, ValidationException
from app.common.responses import PageData
from app.modules.llm_model.models import LlmModel
from app.modules.llm_model.repository import LlmModelRepository
from app.modules.llm_model.schema import (
    LlmModelCreate,
    LlmModelResponse,
    LlmModelUpdate,
)
from app.utils.encrypt_utils import encrypt_api_key


class LlmModelService:
    """Business logic for LLM Model"""

    def __init__(self, repo: LlmModelRepository):
        self.repo = repo

    def _to_response(self, model: LlmModel) -> LlmModelResponse:
        """Domain model -> Response DTO"""
        return LlmModelResponse.model_validate(model)

    async def _get_model_by_id(self, model_id: str, user_id: int) -> LlmModel:
        """Internal: get ORM model by ID"""
        model = await self.repo.get_by_id(model_id, user_id)
        if not model:
            raise NotFoundException("LLM Model", model_id)
        return model

    async def create_model(
        self, user_id: int, data: LlmModelCreate
    ) -> LlmModelResponse:
        """Create a new LLM model"""
        existing = await self.repo.get_by_name(user_id, data.name)
        if existing:
            raise ValidationException(
                f"LLM model with name '{data.name}' already exists"
            )

        if data.is_default:
            await self.repo.clear_default_flags(user_id)

        encrypted_key = None
        if data.api_key:
            encrypted_key = encrypt_api_key(data.api_key)

        model = await self.repo.create(user_id, data, encrypted_api_key=encrypted_key)
        return self._to_response(model)

    async def get_model(self, model_id: str, user_id: int) -> LlmModelResponse:
        """Get a LLM model by ID"""
        model = await self._get_model_by_id(model_id, user_id)
        return self._to_response(model)

    async def list_models(
        self, user_id: int, page: int = 1, page_size: int = 20
    ) -> PageData[LlmModelResponse]:
        """List LLM models with pagination"""
        items, total = await self.repo.list_by_user(user_id, page, page_size)
        return PageData(
            items=[self._to_response(item) for item in items],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def update_model(
        self, model_id: str, user_id: int, data: LlmModelUpdate
    ) -> LlmModelResponse:
        """Update a LLM model"""
        model = await self._get_model_by_id(model_id, user_id)

        if data.is_default:
            await self.repo.clear_default_flags(user_id)

        encrypted_key = None
        if data.api_key:
            encrypted_key = encrypt_api_key(data.api_key)

        updated = await self.repo.update(model, data, encrypted_api_key=encrypted_key)
        return self._to_response(updated)

    async def delete_model(self, model_id: str, user_id: int) -> None:
        """Delete a LLM model"""
        model = await self._get_model_by_id(model_id, user_id)
        await self.repo.delete(model)

    async def get_default_model(self, user_id: int) -> LlmModelResponse | None:
        """Get the default LLM model"""
        model = await self.repo.get_default(user_id)
        if model is None:
            return None
        return self._to_response(model)

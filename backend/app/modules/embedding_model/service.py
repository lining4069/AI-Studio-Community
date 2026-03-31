"""
Embedding Model service for business logic.
"""

from app.common.exceptions import NotFoundException, ValidationException
from app.common.responses import PageData
from app.modules.embedding_model.models import EmbeddingModel, EmbeddingType
from app.modules.embedding_model.repository import EmbeddingModelRepository
from app.modules.embedding_model.schema import (
    EmbeddingModelCreate,
    EmbeddingModelResponse,
    EmbeddingModelUpdate,
)
from app.utils.encrypt_utils import decrypt_api_key, encrypt_api_key


class EmbeddingModelService:
    """Business logic for Embedding Model"""

    def __init__(self, repo: EmbeddingModelRepository):
        self.repo = repo

    def _to_response(self, model: EmbeddingModel) -> EmbeddingModelResponse:
        """Domain model -> Response DTO"""
        return EmbeddingModelResponse.model_validate(model)

    async def _get_model_by_id(self, model_id: str, user_id: int) -> EmbeddingModel:
        """Internal: get ORM model by ID"""
        model = await self.repo.get_by_id(model_id, user_id)
        if not model:
            raise NotFoundException("Embedding Model", model_id)
        return model

    async def create_model(
        self, user_id: int, data: EmbeddingModelCreate
    ) -> EmbeddingModelResponse:
        """Create a new Embedding model.

        For API-based models, probes the embedding endpoint before creation
        to determine whether the API supports custom dimensions.
        """
        existing = await self.repo.get_by_name(user_id, data.name)
        if existing:
            raise ValidationException(
                f"Embedding model with name '{data.name}' already exists"
            )

        if data.is_default:
            await self.repo.clear_default_flags(user_id)

        encrypted_key = None
        if data.api_key:
            encrypted_key = encrypt_api_key(data.api_key)

        # Probe API-based models to detect dimension support
        is_dimensionable = False
        if (
            data.type == EmbeddingType.OPENAI_COMPATIBLE
            and data.dimension is not None
            and data.api_key
        ):
            actual_dim, is_dimensionable = await self._probe_embedding_dimension(
                api_key=decrypt_api_key(data.api_key),
                endpoint=data.endpoint or "",
                model=data.model_name or "text-embedding-3-small",
                requested_dimension=data.dimension,
            )
            if not is_dimensionable:
                # API ignores dimensions param; update to actual dimension
                data.dimension = actual_dim

        model = await self.repo.create(
            user_id,
            data,
            encrypted_api_key=encrypted_key,
            is_dimensionable=is_dimensionable,
        )
        return self._to_response(model)

    async def _probe_embedding_dimension(
        self,
        api_key: str,
        endpoint: str,
        model: str,
        requested_dimension: int,
    ) -> tuple[int, bool]:
        """
        Probe embedding API to determine actual returned dimension.

        Returns:
            Tuple of (actual_dimension, is_dimensionable)
        """
        from app.services.providers.openai_compatible import (
            OpenAICompatibleEmbeddingProvider,
        )

        return await OpenAICompatibleEmbeddingProvider.probe(
            api_key=api_key,
            endpoint=endpoint,
            model=model,
            dimension=requested_dimension,
        )

    async def get_model(self, model_id: str, user_id: int) -> EmbeddingModelResponse:
        """Get an Embedding model by ID"""
        model = await self._get_model_by_id(model_id, user_id)
        return self._to_response(model)

    async def list_models(
        self, user_id: int, page: int = 1, page_size: int = 20
    ) -> PageData[EmbeddingModelResponse]:
        """List Embedding models with pagination"""
        items, total = await self.repo.list_by_user(user_id, page, page_size)
        return PageData(
            items=[self._to_response(item) for item in items],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def update_model(
        self, model_id: str, user_id: int, data: EmbeddingModelUpdate
    ) -> EmbeddingModelResponse:
        """Update an Embedding model"""
        model = await self._get_model_by_id(model_id, user_id)

        if data.is_default:
            await self.repo.clear_default_flags(user_id)

        encrypted_key = None
        if data.api_key:
            encrypted_key = encrypt_api_key(data.api_key)

        updated = await self.repo.update(model, data, encrypted_api_key=encrypted_key)
        return self._to_response(updated)

    async def delete_model(self, model_id: str, user_id: int) -> None:
        """Delete an Embedding model"""
        model = await self._get_model_by_id(model_id, user_id)
        await self.repo.delete(model)

    async def get_default_model(self, user_id: int) -> EmbeddingModelResponse | None:
        """Get the default Embedding model"""
        model = await self.repo.get_default(user_id)
        if model is None:
            return None
        return self._to_response(model)

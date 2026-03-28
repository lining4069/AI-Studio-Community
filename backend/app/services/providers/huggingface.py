"""
HuggingFace Provider Implementation.

Implements providers for HuggingFace embedding models (local mode).
"""
from typing import List, Optional

from loguru import logger

from app.services.providers.base import EmbeddingProvider


class HuggingFaceEmbeddingProvider(EmbeddingProvider):
    """
    HuggingFace Embedding Provider for local model inference.

    Uses sentence-transformers for embedding generation.
    """

    DEFAULT_DIMENSION = 768

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        batch_size: int = 32,
        dimension: Optional[int] = None,
    ):
        self.model_name = model_name
        self.batch_size = batch_size
        self._dimension = dimension or self.DEFAULT_DIMENSION
        self._model = None
        self._pipeline = None

    @property
    def provider_name(self) -> str:
        return "huggingface"

    @property
    def dimension(self) -> int:
        return self._dimension

    def _ensure_model(self):
        """Lazy load the model"""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name)
                # Update dimension from actual model
                self._dimension = self._model.get_sentence_embedding_dimension() or self._dimension
                logger.info(f"Loaded HuggingFace model: {self.model_name}, dimension: {self._dimension}")
            except ImportError:
                logger.error("sentence-transformers not installed. Run: pip install sentence-transformers")
                raise

    async def aembed(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a batch of texts"""
        try:
            self._ensure_model()
            embeddings = self._model.encode(
                texts,
                batch_size=self.batch_size,
                show_progress_bar=False,
                convert_to_numpy=True,
            )
            return embeddings.tolist()
        except Exception as e:
            logger.error(f"HuggingFace embedding error: {e}")
            return [[0.0] * self._dimension for _ in texts]

    async def aembed_query(self, query: str) -> List[float]:
        """Generate embedding for a single query"""
        try:
            self._ensure_model()
            embedding = self._model.encode(
                query,
                batch_size=1,
                show_progress_bar=False,
                convert_to_numpy=True,
            )
            return embedding.tolist()[0]
        except Exception as e:
            logger.error(f"HuggingFace embedding query error: {e}")
            return [0.0] * self._dimension

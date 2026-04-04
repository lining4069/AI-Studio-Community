from typing import Any

from loguru import logger

from app.services.providers.base import RerankerProvider
from app.services.providers.http_client import HttpClient

# ============================================================================
# Cohere-Style Reranker Provider
# ============================================================================


class CohereRerankerProvider(RerankerProvider):
    """
    Cohere-compatible Reranker Provider using httpx.AsyncClient.

    Works with any /v1/rerank endpoint (Cohere, Jina, SiliconFlow, vLLM, etc.)
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "",
        model: str = "cohere-rerank",
        top_n: int | None = None,
    ):
        self.api_key = api_key
        self.model = model
        self.top_n = top_n

        # Set base URL with proper endpoint format
        if not base_url:
            self.base_url = "https://api.cohere.ai/v1/rerank"
        else:
            base_url = base_url.rstrip("/")
            if base_url.endswith("/v1/rerank"):
                self.base_url = base_url
            elif base_url.endswith("/v1"):
                self.base_url = f"{base_url}/rerank"
            else:
                self.base_url = f"{base_url}/v1/rerank"

        # Extract the base URL without /rerank for HttpClient
        base = self.base_url.rsplit("/rerank", 1)[0]
        self._http = HttpClient(api_key=api_key, base_url=base)

    @property
    def provider_name(self) -> str:
        return "openai_compatible"

    async def arerank(
        self,
        query: str,
        documents: list[str],
        top_n: int | None = None,
    ) -> list[dict[str, Any]]:
        """Rerank documents using compatible rerank API"""
        if not documents:
            return []

        n = top_n or self.top_n or len(documents)

        try:
            results = await self._http.rerank(
                model=self.model,
                query=query,
                documents=documents,
                top_n=n,
            )
            return results

        except Exception as e:
            logger.error(f"Rerank error: {e}")
            return self._fallback_rerank(query, documents, n)

    def _fallback_rerank(
        self,
        query: str,
        documents: list[str],
        top_n: int,
    ) -> list[dict[str, Any]]:
        """Simple fallback reranking based on keyword overlap"""
        query_words = set(query.lower().split())
        results = []

        for i, doc in enumerate(documents):
            doc_words = set(doc.lower().split())
            if query_words:
                score = len(query_words & doc_words) / len(query_words)
            else:
                score = 0.0
            results.append(
                {
                    "index": i,
                    "score": score,
                    "document": doc,
                }
            )

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_n]

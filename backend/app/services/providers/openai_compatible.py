"""
OpenAI-Compatible Provider Implementation.

Implements providers for any OpenAI-compatible API endpoint.
Supports standard OpenAI-compatible LLM, Embedding, and Cohere-style Reranker endpoints.
All HTTP calls use httpx.AsyncClient for full control over the request/response lifecycle.
"""

from collections.abc import AsyncGenerator
from typing import Any

from loguru import logger

from app.services.providers.base import EmbeddingProvider, LLMProvider, RerankerProvider
from app.utils.http_client import HttpClient

# ============================================================================
# OpenAI-Compatible LLM Provider
# ============================================================================


class OpenAICompatibleLLMProvider(LLMProvider):
    """
    OpenAI-compatible LLM Provider using httpx.AsyncClient.

    Works with any OpenAI-compatible endpoint (vLLM, LocalAI, SiliconFlow, etc.)
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        temperature: float = 0.1,
        max_tokens: int | None = None,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.temperature = temperature
        self.max_tokens = max_tokens

        # Normalize base_url to ensure proper endpoint
        normalized_base_url = base_url.rstrip("/")
        if not normalized_base_url.endswith("/v1"):
            normalized_base_url += "/v1"

        self._http = HttpClient(
            api_key=api_key,
            base_url=normalized_base_url,
        )

    @property
    def provider_name(self) -> str:
        return "openai_compatible"

    async def astream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """Stream chat completions"""
        try:
            stream_result = await self._http.chat_completions(
                model=self.model,
                messages=messages,
                stream=True,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                tools=tools,
                **kwargs,
            )

            async for chunk in stream_result:
                choices = chunk.get("choices", [])
                if choices:
                    delta = choices[0].get("delta", {})
                    content = delta.get("content")
                    if content:
                        yield content

        except Exception as e:
            logger.error(f"OpenAI-compatible LLM streaming error: {e}")
            yield f"Error: {str(e)}"

    async def achat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs,
    ) -> str:
        """Non-streaming chat completion"""
        try:
            result = await self._http.chat_completions(
                model=self.model,
                messages=messages,
                stream=False,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                tools=tools,
                **kwargs,
            )

            choices = result.get("choices", [])
            if choices and choices[0].get("message", {}).get("content"):
                return choices[0]["message"]["content"]
            return ""

        except Exception as e:
            logger.error(f"OpenAI-compatible LLM error: {e}")
            return f"Error: {str(e)}"


# ============================================================================
# OpenAI-Compatible Embedding Provider
# ============================================================================


class OpenAICompatibleEmbeddingProvider(EmbeddingProvider):
    """
    OpenAI-compatible Embedding Provider using httpx.AsyncClient.

    Works with any OpenAI-compatible embedding endpoint.
    """

    DEFAULT_DIMENSION = 1536

    def __init__(
        self,
        api_key: str,
        endpoint: str = "",
        model: str = "text-embedding-3-small",
        dimension: int | None = None,
        batch_size: int = 10,
    ):
        self.api_key = api_key
        self.endpoint = endpoint
        self.model = model
        self._dimension = dimension or self.DEFAULT_DIMENSION
        self.batch_size = batch_size

        # Normalize base_url for embeddings
        if endpoint:
            base_url = endpoint.rstrip("/")
            if not base_url.endswith("/v1"):
                base_url += "/v1"
        else:
            base_url = "https://api.openai.com/v1"

        self._http = HttpClient(
            api_key=api_key,
            base_url=base_url,
        )

        # Only send dimensions parameter to OpenAI's official endpoint;
        # compatible endpoints (DashScope, vLLM, etc.) may not support it.
        self._is_openai_official = "api.openai.com" in base_url

    @property
    def provider_name(self) -> str:
        return "openai_compatible"

    @property
    def dimension(self) -> int:
        return self._dimension

    async def aembed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts"""
        try:
            # Only send dimensions to OpenAI's official endpoint; DashScope and
            # other compatible endpoints may not support it or may ignore it.
            dims = self._dimension if self._is_openai_official else None
            embeddings = await self._http.embeddings(
                model=self.model,
                input=texts,
                dimensions=dims,
            )
            # Validate returned dimension matches expectation
            if embeddings and len(embeddings[0]) != self._dimension:
                logger.warning(
                    f"Embedding dimension mismatch: expected {self._dimension}, "
                    f"got {len(embeddings[0])}"
                )
            return embeddings
        except Exception as e:
            logger.error(f"OpenAI-compatible embedding error: {e}")
            return [[0.0] * self._dimension for _ in texts]

    async def aembed_query(self, query: str) -> list[float]:
        """Generate embedding for a single query"""
        try:
            dims = self._dimension if self._is_openai_official else None
            embeddings = await self._http.embeddings(
                model=self.model,
                input=[query],
                dimensions=dims,
            )
            result = embeddings[0] if embeddings else [0.0] * self._dimension
            if result and len(result) != self._dimension:
                logger.warning(
                    f"Query embedding dimension mismatch: expected {self._dimension}, "
                    f"got {len(result)}"
                )
            return result
        except Exception as e:
            logger.error(f"OpenAI-compatible embedding query error: {e}")
            return [0.0] * self._dimension


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

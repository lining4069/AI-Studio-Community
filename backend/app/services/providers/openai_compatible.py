"""
OpenAI-Compatible Provider Implementation.

Implements providers for any OpenAI-compatible API endpoint.
Supports standard OpenAI-compatible LLM, Embedding, and Cohere-style Reranker endpoints.
"""

from collections.abc import AsyncGenerator
from typing import Any

from loguru import logger
from openai import AsyncOpenAI

from app.services.providers.base import EmbeddingProvider, LLMProvider, RerankerProvider
from app.utils.aiohttp_session import HttpSessionShared

# ============================================================================
# OpenAI-Compatible LLM Provider
# ============================================================================


class OpenAICompatibleLLMProvider(LLMProvider):
    """
    OpenAI-compatible LLM Provider using official OpenAI AsyncOpenAI.

    Works with any OpenAI-compatible endpoint (vLLM, LocalAI, etc.)
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

        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=normalized_base_url,
            temperature=temperature,
            max_tokens=max_tokens,
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
            request_kwargs = {
                "model": self.model,
                "messages": messages,
                "stream": True,
                "temperature": self.temperature,
            }
            if self.max_tokens:
                request_kwargs["max_tokens"] = self.max_tokens
            if tools:
                request_kwargs["tools"] = tools

            stream = await self._client.chat.completions.create(**request_kwargs)

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

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
            request_kwargs = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "temperature": self.temperature,
            }
            if self.max_tokens:
                request_kwargs["max_tokens"] = self.max_tokens
            if tools:
                request_kwargs["tools"] = tools

            response = await self._client.chat.completions.create(**request_kwargs)

            if response.choices and response.choices[0].message.content:
                return response.choices[0].message.content
            return ""

        except Exception as e:
            logger.error(f"OpenAI-compatible LLM error: {e}")
            return f"Error: {str(e)}"


# ============================================================================
# OpenAI-Compatible Embedding Provider
# ============================================================================


class OpenAICompatibleEmbeddingProvider(EmbeddingProvider):
    """
    OpenAI-compatible Embedding Provider using official OpenAI AsyncOpenAI.

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

        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
        )

    @property
    def provider_name(self) -> str:
        return "openai_compatible"

    @property
    def dimension(self) -> int:
        return self._dimension

    async def aembed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts"""
        try:
            response = await self._client.embeddings.create(
                model=self.model,
                input=texts,
                dimensions=self._dimension,
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            logger.error(f"OpenAI-compatible embedding error: {e}")
            return [[0.0] * self._dimension for _ in texts]

    async def aembed_query(self, query: str) -> list[float]:
        """Generate embedding for a single query"""
        try:
            response = await self._client.embeddings.create(
                model=self.model,
                input=[query],
                dimensions=self._dimension,
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"OpenAI-compatible embedding query error: {e}")
            return [0.0] * self._dimension


# ============================================================================
# Cohere-Style Reranker Provider
# ============================================================================


class CohereRerankerProvider(RerankerProvider):
    """
    Cohere-compatible Reranker Provider.

    Works with any /v1/rerank endpoint (Cohere, Jina, vLLM, etc.)
    Reference: PAI-RAG backend/rag/rerank/reranker.py
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
        import aiohttp

        if not documents:
            return []

        n = top_n or self.top_n or len(documents)

        # Standard rerank API format
        payload = {
            "model": self.model,
            "query": query,
            "documents": documents,
            "top_n": n,
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        try:
            session = await HttpSessionShared.ensure_session()
            async with session.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Rerank API error: {response.status} - {error_text}")
                    return self._fallback_rerank(query, documents, n)

                result = await response.json()

                # Parse response - may be Cohere format or Jina format
                if "results" in result:
                    raw_results = result["results"]
                elif "output" in result and "results" in result["output"]:
                    raw_results = result["output"]["results"]
                else:
                    logger.error(f"Unexpected rerank response format: {result}")
                    return self._fallback_rerank(query, documents, n)

                # Transform to standard format
                rerank_results = []
                for item in raw_results:
                    index = item.get("index", 0)
                    score = item.get("relevance_score", item.get("score", 0.0))

                    # Extract document text
                    if "document" in item and isinstance(item["document"], dict):
                        doc_text = item["document"].get("text", "")
                    elif "text" in item:
                        doc_text = item["text"]
                    else:
                        doc_text = (
                            documents[index] if 0 <= index < len(documents) else ""
                        )

                    rerank_results.append(
                        {
                            "index": index,
                            "score": score,
                            "document": doc_text,
                        }
                    )

                # Sort by score descending
                rerank_results.sort(key=lambda x: x["score"], reverse=True)
                return rerank_results

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

"""
HTTP Client based on httpx.AsyncClient.

Provides a unified HTTP client for LLM/Embedding/Rerank API calls,
replacing the official OpenAI SDK (AsyncOpenAI) and aiohttp usage.
"""

from collections.abc import AsyncGenerator
from typing import Any

import httpx

DEFAULT_TIMEOUT = 30.0


class HttpClient:
    """
    Unified HTTP client for model API calls.

    Wraps httpx.AsyncClient to provide chat completions, embeddings,
    and rerank methods with consistent error handling and timeout management.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "",
        timeout: float = DEFAULT_TIMEOUT,
    ):
        """
        Initialize HTTP client.

        Args:
            api_key: API key for Authorization header
            base_url: Base URL for all requests (will be stripped of trailing slash)
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip("/") if base_url else ""
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def ensure_client(self) -> httpx.AsyncClient:
        """Get or create the httpx AsyncClient instance."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout),
                headers=self._build_headers(),
            )
        return self._client

    def _build_headers(self) -> dict[str, str]:
        """Build common headers including Authorization."""
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    # -------------------------------------------------------------------------
    # Chat Completions
    # -------------------------------------------------------------------------

    async def chat_completions(
        self,
        model: str,
        messages: list[dict[str, Any]],
        stream: bool = False,
        temperature: float = 0.1,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> dict | AsyncGenerator[dict, None]:
        """
        Call chat completions endpoint.

        Args:
            model: Model name
            messages: List of message dicts
            stream: Whether to stream response
            temperature: Sampling temperature
            max_tokens: Max tokens to generate
            tools: Optional tools/function definitions
            **kwargs: Additional request parameters

        Returns:
            Response dict (non-stream) or AsyncGenerator of chunk dicts (stream)
        """
        client = await self.ensure_client()

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": stream,
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if tools:
            payload["tools"] = tools
        payload.update(kwargs)

        if stream:
            return self._stream_chat_completions(client, payload)
        else:
            response = await client.post("/chat/completions", json=payload)
            response.raise_for_status()
            return response.json()

    async def _stream_chat_completions(
        self,
        client: httpx.AsyncClient,
        payload: dict[str, Any],
    ) -> AsyncGenerator[dict, None]:
        """Internal: stream chat completions via SSE."""
        async with client.stream("POST", "/chat/completions", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                import json as _json

                try:
                    chunk = _json.loads(data)
                except Exception:
                    continue
                yield chunk

    # -------------------------------------------------------------------------
    # Embeddings
    # -------------------------------------------------------------------------

    async def embeddings(
        self,
        model: str,
        input: list[str],
        dimensions: int | None = None,
        **kwargs: Any,
    ) -> list[list[float]]:
        """
        Call embeddings endpoint.

        Args:
            model: Model name
            input: List of texts to embed
            dimensions: Optional embedding dimensions
            **kwargs: Additional request parameters

        Returns:
            List of embedding vectors (list of floats)
        """
        client = await self.ensure_client()

        payload: dict[str, Any] = {"model": model, "input": input}
        if dimensions is not None:
            payload["dimensions"] = dimensions
        payload.update(kwargs)

        response = await client.post("/embeddings", json=payload)
        response.raise_for_status()
        result = response.json()

        return [item["embedding"] for item in result.get("data", [])]

    # -------------------------------------------------------------------------
    # Rerank
    # -------------------------------------------------------------------------

    async def rerank(
        self,
        model: str,
        query: str,
        documents: list[str],
        top_n: int,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """
        Call rerank endpoint (Cohere-compatible /v1/rerank format).

        Args:
            model: Model name
            query: Query string
            documents: List of documents to rerank
            top_n: Number of top results to return
            **kwargs: Additional request parameters

        Returns:
            List of rerank result dicts with index, score, and document
        """
        client = await self.ensure_client()

        payload: dict[str, Any] = {
            "model": model,
            "query": query,
            "documents": documents,
            "top_n": top_n,
        }
        payload.update(kwargs)

        response = await client.post("/rerank", json=payload)
        response.raise_for_status()
        result = response.json()

        # Parse Cohere-compatible response format
        if "results" in result:
            raw_results = result["results"]
        elif "output" in result and "results" in result.get("output", {}):
            raw_results = result["output"]["results"]
        else:
            raw_results = []

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
                doc_text = documents[index] if 0 <= index < len(documents) else ""

            rerank_results.append(
                {
                    "index": index,
                    "score": score,
                    "document": doc_text,
                }
            )

        rerank_results.sort(key=lambda x: x["score"], reverse=True)
        return rerank_results

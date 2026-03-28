"""
DashScope Provider Implementation.

Implements providers for DashScope (Alibaba Cloud) LLM, Embedding, and Reranker services.
Reference: PAI-RAG backend/rag/rerank/dashscope_reranker.py
"""

from collections.abc import AsyncGenerator
from typing import Any

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from loguru import logger

from app.services.providers.base import EmbeddingProvider, LLMProvider, RerankerProvider
from app.utils.aiohttp_session import HttpSessionShared

# ============================================================================
# DashScope LLM Provider
# ============================================================================


class DashScopeLLMProvider(LLMProvider):
    """
    DashScope LLM Provider using LangChain ChatOpenAI.

    Supports DashScope's Qwen models via OpenAI-compatible API.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "qwen-max",
        temperature: float = 0.1,
        max_tokens: int | None = None,
    ):
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

        self._client = ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            temperature=temperature,
            max_tokens=max_tokens,
            streaming=True,
        )

    @property
    def provider_name(self) -> str:
        return "dashscope"

    async def astream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """Stream chat completions from DashScope"""
        # LangChain's astream is async, we need to convert sync to async generator
        # The ChatOpenAI from langchain_openai supports async streaming
        try:
            from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

            # Convert messages dict to LangChain format
            langchain_messages = []
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")

                if role == "system":
                    langchain_messages.append(SystemMessage(content=content))
                elif role == "user":
                    langchain_messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    langchain_messages.append(AIMessage(content=content))
                else:
                    langchain_messages.append(HumanMessage(content=content))

            # Use astream which is async
            async for chunk in self._client.astream(langchain_messages):
                if chunk.content:
                    yield chunk.content

        except Exception as e:
            logger.error(f"DashScope LLM streaming error: {e}")
            yield f"Error: {str(e)}"

    async def achat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs,
    ) -> str:
        """Non-streaming chat completion from DashScope"""
        try:
            from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

            langchain_messages = []
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")

                if role == "system":
                    langchain_messages.append(SystemMessage(content=content))
                elif role == "user":
                    langchain_messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    langchain_messages.append(AIMessage(content=content))
                else:
                    langchain_messages.append(HumanMessage(content=content))

            response = await self._client.ainvoke(langchain_messages)
            return response.content

        except Exception as e:
            logger.error(f"DashScope LLM error: {e}")
            return f"Error: {str(e)}"


# ============================================================================
# DashScope Embedding Provider
# ============================================================================


class DashScopeEmbeddingProvider(EmbeddingProvider):
    """
    DashScope Embedding Provider using LangChain OpenAIEmbeddings.

    Supports DashScope's text-embedding-v3 model.
    """

    DEFAULT_DIMENSION = 1536

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-v3",
        dimension: int | None = None,
        batch_size: int = 10,
    ):
        self.api_key = api_key
        self.model = model
        self._dimension = dimension or self.DEFAULT_DIMENSION
        self.batch_size = batch_size

        self._client = OpenAIEmbeddings(
            model=model,
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            dimensions=self._dimension,
        )

    @property
    def provider_name(self) -> str:
        return "dashscope"

    @property
    def dimension(self) -> int:
        return self._dimension

    async def aembed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts"""
        try:
            embeddings = await self._client.aembed_documents(texts)
            return embeddings
        except Exception as e:
            logger.error(f"DashScope embedding error: {e}")
            # Return zero vectors on error
            return [[0.0] * self._dimension for _ in texts]

    async def aembed_query(self, query: str) -> list[float]:
        """Generate embedding for a single query"""
        try:
            embedding = await self._client.aembed_query(query)
            return embedding
        except Exception as e:
            logger.error(f"DashScope embedding query error: {e}")
            return [0.0] * self._dimension


# ============================================================================
# DashScope Reranker Provider
# ============================================================================


class DashScopeRerankerProvider(RerankerProvider):
    """
    DashScope Reranker Provider.

    Implements reranking using DashScope text-rerank API.
    Reference: PAI-RAG backend/rag/rerank/dashscope_reranker.py
    """

    def __init__(
        self,
        api_key: str,
        model: str = "qwen3-rerank",
        base_url: str = "",
        top_n: int | None = None,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = (
            base_url
            or "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"
        )
        self.top_n = top_n

        # Ensure proper endpoint format
        if not self.base_url.endswith("/text-rerank/text-rerank"):
            if self.base_url.endswith("/text-rerank"):
                self.base_url = f"{self.base_url}/text-rerank"
            else:
                self.base_url = f"{self.base_url}/text-rerank/text-rerank"

    @property
    def provider_name(self) -> str:
        return "dashscope"

    async def arerank(
        self,
        query: str,
        documents: list[str],
        top_n: int | None = None,
    ) -> list[dict[str, Any]]:
        """Rerank documents using DashScope API"""
        import aiohttp

        if not documents:
            return []

        n = top_n or self.top_n or len(documents)

        # Prepare request payload for DashScope
        payload = {
            "model": self.model,
            "input": {
                "query": query,
                "documents": documents,
            },
            "parameters": {
                "return_documents": True,
                "top_n": n,
            },
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
                    logger.error(
                        f"DashScope rerank API error: {response.status} - {error_text}"
                    )
                    return self._fallback_rerank(query, documents, n)

                result = await response.json()

                # Parse DashScope response format
                if "output" in result and "results" in result["output"]:
                    raw_results = result["output"]["results"]
                elif "results" in result:
                    raw_results = result["results"]
                else:
                    logger.error(
                        f"Unexpected DashScope rerank response format: {result}"
                    )
                    return self._fallback_rerank(query, documents, n)

                # Transform to standard format
                rerank_results = []
                for item in raw_results:
                    index = item.get("index", 0)
                    score = item.get("relevance_score", 0.0)

                    # Extract document text
                    if "document" in item and isinstance(item["document"], dict):
                        doc_text = item["document"].get("text", "")
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
                return rerank_results[:n]

        except Exception as e:
            logger.error(f"DashScope rerank error: {e}")
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
            # Simple Jaccard-like similarity
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

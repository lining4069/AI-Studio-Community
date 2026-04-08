"""
Tests for RAGRetrievalTool.

Validates knowledge base retrieval functionality.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.agent.tools.rag_tool import RAGRetrievalTool


class TestRAGRetrievalTool:
    """Test RAGRetrievalTool functionality."""

    @pytest.mark.asyncio
    async def test_init_with_kb_ids(self):
        """Test tool initializes with kb_ids."""
        tool = RAGRetrievalTool(kb_ids=["kb-1", "kb-2"], top_k=5)

        assert tool.kb_ids == ["kb-1", "kb-2"]
        assert tool.top_k == 5

    @pytest.mark.asyncio
    async def test_set_rag_service(self):
        """Test setting RAG service."""
        tool = RAGRetrievalTool(kb_ids=["kb-1"])
        mock_service = MagicMock()
        mock_service.retrieve = AsyncMock()

        tool.set_rag_service(mock_service)

        assert tool._rag_service is mock_service

    @pytest.mark.asyncio
    async def test_run_without_service_returns_error(self):
        """Test run returns error when service not configured."""
        tool = RAGRetrievalTool(kb_ids=["kb-1"])

        result = await tool.run({"query": "test"})

        assert "error" in result
        assert result["results"] == []

    @pytest.mark.asyncio
    async def test_run_with_service(self):
        """Test run with configured service."""
        tool = RAGRetrievalTool(kb_ids=["kb-1"])

        # Mock RAG service
        mock_result = MagicMock()
        mock_result.chunk_id = "chunk-1"
        mock_result.content = "Test content"
        mock_result.score = 0.95
        mock_result.metadata = {"source": "doc1"}

        mock_service = MagicMock()
        mock_service.retrieve = AsyncMock(return_value=[mock_result])
        tool.set_rag_service(mock_service)

        result = await tool.run({"query": "test", "top_k": 3})

        assert "results" in result
        assert len(result["results"]) == 1
        assert result["results"][0]["chunk_id"] == "chunk-1"
        assert result["results"][0]["content"] == "Test content"

    @pytest.mark.asyncio
    async def test_run_respects_top_k_parameter(self):
        """Test top_k parameter from input."""
        tool = RAGRetrievalTool(kb_ids=["kb-1"], top_k=5)

        mock_service = MagicMock()
        mock_service.retrieve = AsyncMock()
        tool.set_rag_service(mock_service)

        await tool.run({"query": "test", "top_k": 10})

        # Verify retrieve was called with top_k=10
        mock_service.retrieve.assert_called_once()
        call_kwargs = mock_service.retrieve.call_args[1]
        assert call_kwargs["top_k"] == 10

    @pytest.mark.asyncio
    async def test_run_uses_default_top_k(self):
        """Test default top_k is used when not specified."""
        tool = RAGRetrievalTool(kb_ids=["kb-1"], top_k=5)

        mock_service = MagicMock()
        mock_service.retrieve = AsyncMock()
        tool.set_rag_service(mock_service)

        await tool.run({"query": "test"})  # No top_k specified

        call_kwargs = mock_service.retrieve.call_args[1]
        assert call_kwargs["top_k"] == 5  # Default from tool

    @pytest.mark.asyncio
    async def test_run_service_exception(self):
        """Test exception from service returns error."""
        tool = RAGRetrievalTool(kb_ids=["kb-1"])

        mock_service = MagicMock()
        mock_service.retrieve = AsyncMock(side_effect=Exception("Service error"))
        tool.set_rag_service(mock_service)

        result = await tool.run({"query": "test"})

        assert "error" in result
        assert "Service error" in result["error"]


class TestRAGRetrievalToolSchema:
    """Test RAGRetrievalTool schema."""

    def test_tool_name(self):
        """Tool has correct name."""
        tool = RAGRetrievalTool(kb_ids=[])
        assert tool.name == "kb_retrieval"

    def test_input_schema_requires_kb_ids_and_query(self):
        """Input schema requires kb_ids and query."""
        tool = RAGRetrievalTool(kb_ids=[])
        schema = tool.input_schema

        assert "kb_ids" in schema["required"]
        assert "query" in schema["required"]
        assert schema["properties"]["kb_ids"]["type"] == "array"
        assert schema["properties"]["query"]["type"] == "string"

    def test_top_k_has_default(self):
        """top_k has a default value."""
        tool = RAGRetrievalTool(kb_ids=[])
        schema = tool.input_schema

        assert "top_k" in schema["properties"]
        assert schema["properties"]["top_k"]["default"] == 5

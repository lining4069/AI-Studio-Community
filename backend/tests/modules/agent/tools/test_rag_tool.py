import pytest
from app.modules.agent.tools.rag_tool import RAGRetrievalTool


def test_rag_tool_name():
    """RAG tool has correct name."""
    tool = RAGRetrievalTool(kb_ids=["kb1"], top_k=5)
    assert tool.name == "kb_retrieval"


def test_rag_tool_schema():
    """RAG tool has correct schema."""
    tool = RAGRetrievalTool(kb_ids=["kb1"], top_k=5)
    assert "kb_ids" in tool.schema["properties"]
    assert "query" in tool.schema["properties"]
    assert "top_k" in tool.schema["properties"]
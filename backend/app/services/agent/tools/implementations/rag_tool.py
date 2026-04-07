"""RAG retrieval tool for querying knowledge bases."""

from typing import Any

from app.services.agent.tools.base import Tool


class RAGRetrievalTool(Tool):
    """
    Tool for retrieving documents from knowledge bases.

    Integrates with existing RAG retrieval pipeline.
    """

    name: str = "kb_retrieval"
    description: str = (
        "Retrieve relevant documents from knowledge bases. "
        "Use this when the user asks about information that might be in the knowledge base. "
        "Returns the most relevant document chunks with scores."
    )
    input_schema: dict = {
        "type": "object",
        "properties": {
            "kb_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of knowledge base IDs to search",
            },
            "query": {
                "type": "string",
                "description": "Search query text",
            },
            "top_k": {
                "type": "integer",
                "description": "Maximum number of results to return",
                "default": 5,
            },
        },
        "required": ["kb_ids", "query"],
    }

    def __init__(self, kb_ids: list[str], top_k: int = 5):
        """
        Initialize RAG retrieval tool.

        Args:
            kb_ids: List of knowledge base IDs to search
            top_k: Maximum number of results
        """
        self.kb_ids = kb_ids
        self.top_k = top_k
        # rag_service will be injected during execution
        self._rag_service = None

    def set_rag_service(self, rag_service: Any) -> None:
        """Set the RAG retrieval service (injected by factory)."""
        self._rag_service = rag_service

    async def run(self, input: dict) -> dict:
        """
        Retrieve documents from knowledge bases.

        Args:
            input: dict with "query", optional "top_k"

        Returns:
            dict with "results" list of {chunk_id, content, score, metadata}
        """
        if self._rag_service is None:
            return {"error": "RAG service not configured", "results": []}

        query = input.get("query", "")
        top_k = input.get("top_k", self.top_k)

        try:
            results = await self._rag_service.retrieve(
                query=query,
                top_k=top_k,
            )
            return {
                "results": [
                    {
                        "chunk_id": r.chunk_id,
                        "content": r.content,
                        "score": r.score,
                        "metadata": r.metadata,
                    }
                    for r in results
                ],
                "query": query,
                "total": len(results),
            }
        except Exception as e:
            return {"error": str(e), "results": []}

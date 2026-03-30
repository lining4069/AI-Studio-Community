"""
Knowledge Base tool for Agent.

Provides tool for querying knowledge bases.
"""

from app.modules.agent.tools.base import BaseTool, ToolDefinition, ToolResult
from app.modules.knowledge_base.repository import KbDocumentRepository
from app.services.rag.service_factory import get_rag_service


class KnowledgeBaseTool(BaseTool):
    """Tool for querying a knowledge base"""

    def __init__(
        self,
        kb_id: str,
        kb_name: str,
        kb_description: str,
        user_id: int,
        db,
        retrieval_top_k: int = 5,
    ):
        """
        Initialize KnowledgeBaseTool.

        Args:
            kb_id: Knowledge base ID
            kb_name: Knowledge base name (for tool description)
            kb_description: Knowledge base description
            user_id: User ID for authorization
            db: Database session
            retrieval_top_k: Number of results to retrieve
        """
        name = f"knowledge_base_{kb_id[:8]}"
        description = (
            f"从知识库「{kb_name}」中搜索与问题相关的内容。\n"
            f"知识库描述：{kb_description}\n"
            f"当你需要从知识库中查找信息时使用此工具。\n"
            f"输入参数为搜索查询语句（query）。"
        )
        super().__init__(name, description)
        self.kb_id = kb_id
        self.kb_name = kb_name
        self.user_id = user_id
        self.db = db
        self.retrieval_top_k = retrieval_top_k

    async def execute(self, query: str, **kwargs) -> ToolResult:
        """
        Execute knowledge base search.

        Args:
            query: Search query string

        Returns:
            ToolResult with search results
        """
        try:
            # Get KB document
            doc_repo = KbDocumentRepository(self.db)
            kb = await doc_repo.get_by_id(self.kb_id, self.user_id)
            if not kb:
                return ToolResult.failure("知识库不存在或无权限访问")

            # Get RAG service
            rag_service = await get_rag_service(kb)
            vector_store = rag_service.get_vector_store(kb.collection_name, kb.user_id)

            # Perform hybrid search
            results = vector_store.hybrid_search(
                query=query,
                k=self.retrieval_top_k,
                vector_weight=kb.vector_weight,
            )

            if not results:
                return ToolResult.ok("知识库中未找到相关内容")

            # Format results
            formatted_results = []
            for i, (_chunk_id, content, score) in enumerate(
                results[: self.retrieval_top_k], 1
            ):
                formatted_results.append(
                    f"[{i}] (相关度: {score:.3f})\n{content[:500]}..."
                )

            content = "\n\n".join(formatted_results)
            return ToolResult.ok(
                content, metadata={"kb_id": self.kb_id, "result_count": len(results)}
            )

        except Exception as e:
            return ToolResult.failure(f"知识库检索失败: {str(e)}")

    def get_definition(self) -> ToolDefinition:
        """Get tool definition for OpenAI function calling"""
        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索查询语句，描述你想要查找的信息",
                    },
                },
                "required": ["query"],
            },
        )


async def create_kb_tools(
    kb_ids: list[str],
    user_id: int,
    db,
    retrieval_top_k: int = 5,
) -> list[KnowledgeBaseTool]:
    """
    Create KnowledgeBaseTool instances for multiple knowledge bases.

    Args:
        kb_ids: List of knowledge base IDs
        user_id: User ID
        db: Database session
        retrieval_top_k: Number of results per KB

    Returns:
        List of KnowledgeBaseTool instances
    """
    if not kb_ids:
        return []

    doc_repo = KbDocumentRepository(db)
    tools = []

    for kb_id in kb_ids:
        kb = await doc_repo.get_by_id(kb_id, user_id)
        if kb and kb.is_active:
            tool = KnowledgeBaseTool(
                kb_id=kb.id,
                kb_name=kb.name,
                kb_description=kb.description or "",
                user_id=user_id,
                db=db,
                retrieval_top_k=retrieval_top_k,
            )
            tools.append(tool)

    return tools

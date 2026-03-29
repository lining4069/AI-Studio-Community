"""
Web Search tool for Agent.

Provides tool for web search using configurable providers (Tavily, etc.).
"""

from app.modules.agent.models import WebSearchProvider
from app.modules.agent.tools.base import BaseTool, ToolDefinition, ToolResult
from app.utils.encrypt_utils import decrypt_api_key


class WebSearchTool(BaseTool):
    """Tool for web search using Tavily"""

    def __init__(
        self,
        api_key: str,
        provider: str = WebSearchProvider.TAVILY.value,
        search_count: int = 10,
    ):
        """
        Initialize WebSearchTool.

        Args:
            api_key: API key for the search provider
            provider: Search provider type (default: tavily)
            search_count: Number of results to return
        """
        name = f"{provider}_websearch"
        description = (
            f"从{self._get_provider_name(provider)}搜索引擎中搜索最新内容。\n"
            f"当你需要查找最新信息、新闻或网络资源时使用此工具。\n"
            f"输入参数为搜索查询语句（query）。"
        )
        super().__init__(name, description)
        self.api_key = api_key
        self.provider = provider
        self.search_count = search_count
        self._client = None

    def _get_provider_name(self, provider: str) -> str:
        """Get human-readable provider name"""
        names = {
            WebSearchProvider.TAVILY.value: "Tavily",
            WebSearchProvider.ALIYUN.value: "阿里云",
        }
        return names.get(provider, provider)

    async def _get_client(self):
        """Get or create the search client"""
        if self._client is None:
            if self.provider == WebSearchProvider.TAVILY.value:
                try:
                    from tavily import AsyncTavilyClient

                    self._client = AsyncTavilyClient(api_key=self.api_key)
                except ImportError:
                    raise ImportError(
                        "tavily package not installed. Install with: pip install tavily-python"
                    ) from None
            elif self.provider == WebSearchProvider.ALIYUN.value:
                # Aliyun search would use their SDK
                raise NotImplementedError("Aliyun search not yet implemented")
            else:
                raise ValueError(f"Unknown search provider: {self.provider}")
        return self._client

    async def execute(self, query: str, **kwargs) -> ToolResult:
        """
        Execute web search.

        Args:
            query: Search query string

        Returns:
            ToolResult with search results
        """
        try:
            await self._get_client()

            if self.provider == WebSearchProvider.TAVILY.value:
                return await self._tavily_search(query)
            elif self.provider == WebSearchProvider.ALIYUN.value:
                return await self._aliyun_search(query)
            else:
                return ToolResult.failure(f"Unknown provider: {self.provider}")

        except ImportError as e:
            return ToolResult.failure(f"依赖未安装: {str(e)}")
        except Exception as e:
            return ToolResult.failure(f"搜索失败: {str(e)}")

    async def _tavily_search(self, query: str) -> ToolResult:
        """Execute Tavily search"""
        # Truncate query to 400 chars (Tavily limit)
        truncated_query = query[:400]

        results = await self._client.search(
            query=truncated_query,
            max_results=self.search_count,
            search_depth="basic",
            topic="general",
        )

        if not results.get("results"):
            return ToolResult.ok("未找到相关搜索结果")

        # Format results
        formatted_results = []
        for i, result in enumerate(results["results"][: self.search_count], 1):
            title = result.get("title", "无标题")
            url = result.get("url", "")
            content = result.get("content", "")[:500]  # Truncate content

            formatted_results.append(f"[{i}] {title}\n来源: {url}\n摘要: {content}...")

        content = "\n\n".join(formatted_results)
        return ToolResult.ok(content, metadata={"result_count": len(formatted_results)})

    async def _aliyun_search(self, query: str) -> ToolResult:
        """Execute Aliyun search (placeholder)"""
        # TODO: Implement Aliyun search
        return ToolResult.failure("阿里云搜索暂未实现")

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


def create_websearch_tool(
    api_key: str,
    provider: str = WebSearchProvider.TAVILY.value,
    search_count: int = 10,
) -> WebSearchTool:
    """
    Create a WebSearchTool instance.

    Args:
        api_key: Decrypted API key
        provider: Search provider
        search_count: Number of results

    Returns:
        WebSearchTool instance
    """
    return WebSearchTool(
        api_key=api_key,
        provider=provider,
        search_count=search_count,
    )


def create_websearch_tool_from_config(
    encrypted_api_key: str,
    provider: str,
    search_count: int = 10,
) -> WebSearchTool:
    """
    Create a WebSearchTool from encrypted config.

    Args:
        encrypted_api_key: Encrypted API key
        provider: Search provider
        search_count: Number of results

    Returns:
        WebSearchTool instance
    """
    api_key = decrypt_api_key(encrypted_api_key)
    return create_websearch_tool(api_key, provider, search_count)

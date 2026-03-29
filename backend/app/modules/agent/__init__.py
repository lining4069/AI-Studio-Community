"""
Agent Module.

Provides:
- Agent entity with tool-calling capabilities
- ReAct (Reasoning + Acting) agent loop
- Knowledge base tools
- Web search tools (Tavily)
- MCP (Model Context Protocol) tool support
- Streaming chat API

Design:
1. **Agent-isolated LLM parameters**: Each agent has its own temperature,
   max_tokens, top_p, etc. that override the base model's defaults.

2. **Knowledge Base mounting modes**:
   - FORCE: Agent always queries KB (becomes RAG assistant)
   - INTENT: Agent decides when to query KB (KB acts as a tool)

3. **Tool system**: Based on OpenAI function calling format, with:
   - BaseTool abstract class
   - ToolRegistry for management
   - ToolDefinition for LLM function specs

4. **MCP integration**: Support for MCP servers as tool sources
"""

from app.modules.agent.agent import AgentConfig, AgentMessage, AgentState, ReactAgent
from app.modules.agent.models import (
    Agent,
    AgentSession,
    KbRetrievalMode,
    McpConnectionType,
    McpServer,
    WebSearchConfig,
    WebSearchProvider,
)
from app.modules.agent.router import router as agent_router
from app.modules.agent.schema import (
    AgentCreate,
    AgentResponse,
    AgentUpdate,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    McpServerCreate,
    McpServerResponse,
    McpServerUpdate,
    ToolCallResult,
    ToolDefinition,
    ToolExecutionRequest,
    ToolExecutionResponse,
    WebSearchConfigCreate,
    WebSearchConfigResponse,
    WebSearchConfigUpdate,
)
from app.modules.agent.service import AgentService

__all__ = [
    # Models
    "Agent",
    "AgentSession",
    "WebSearchConfig",
    "McpServer",
    "KbRetrievalMode",
    "WebSearchProvider",
    "McpConnectionType",
    # Schemas
    "AgentCreate",
    "AgentUpdate",
    "AgentResponse",
    "ChatRequest",
    "ChatMessage",
    "ChatResponse",
    "ToolCallResult",
    "ToolDefinition",
    "ToolExecutionRequest",
    "ToolExecutionResponse",
    "WebSearchConfigCreate",
    "WebSearchConfigUpdate",
    "WebSearchConfigResponse",
    "McpServerCreate",
    "McpServerUpdate",
    "McpServerResponse",
    # Service
    "AgentService",
    # Agent
    "ReactAgent",
    "AgentConfig",
    "AgentMessage",
    "AgentState",
    # Router
    "agent_router",
]

"""
AgentFactory - creates Agent instances based on config.agent_type.

Replaces simple if-else with a factory pattern for extensibility.
"""

from app.modules.agent.domain import DomainConfig
from app.modules.agent.tools.base import Tool
from app.services.agent.react_agent import ReactAgent
from app.services.agent.simple_agent import SimpleAgent
from app.services.providers.base import LLMProvider


def create_agent(
    agent_type: str,
    tools: list[Tool],
    llm: LLMProvider,
    run_id: str | None,
    config: DomainConfig | None = None,
) -> SimpleAgent | ReactAgent:
    """
    Create an Agent instance based on agent_type.

    Args:
        agent_type: Type of agent ("simple" or "react")
        tools: List of Tool instances
        llm: LLM provider
        run_id: Run identifier for SSE event tracking
        config: Optional DomainConfig for system prompt / max loop

    Returns:
        Agent instance (SimpleAgent or ReactAgent)
    """
    max_loop = config.max_loop if config else 5
    system_prompt = config.system_prompt if config else None

    if agent_type == "react":
        return ReactAgent(
            llm=llm,
            tools=tools,
            max_loop=max_loop,
            system_prompt=system_prompt,
            run_id=run_id,
        )

    # Default to simple
    return SimpleAgent(
        llm=llm,
        tools=tools,
        system_prompt=system_prompt,
        run_id=run_id,
    )

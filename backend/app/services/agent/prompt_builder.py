"""
Prompt builder for constructing LLM messages with memory.

Builds: [summary] + [recent messages] + [tools] + [user input]
"""
from typing import Any


def build_system_prompt(
    summary: str | None = None,
    tools: list[dict] | None = None,
) -> str:
    """
    Build the system prompt with memory and tools.

    Args:
        summary: Conversation summary from previous turns
        tools: List of available tools for function calling

    Returns:
        Formatted system prompt string
    """
    parts = [
        "You are an AI Assistant with knowledge base access.",
        "Provide accurate, helpful responses based on available information.",
    ]

    if summary:
        parts.append(f"\nPrevious Conversation Summary:\n{summary}")

    if tools:
        parts.append("\nAvailable Tools:")
        for tool in tools:
            parts.append(
                f"- {tool['name']}: {tool['description']} "
                f"(params: {tool.get('parameters', {})})"
            )

    return "\n".join(parts)


def build_messages(
    user_input: str,
    history: list[dict[str, str]] | None = None,
    system_prompt: str | None = None,
) -> list[dict[str, Any]]:
    """
    Build message list for LLM.

    Args:
        user_input: Current user input
        history: Previous messages [(role, content), ...]
        system_prompt: Optional system prompt override

    Returns:
        List of message dicts for LLM
    """
    messages = []

    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    # Add history messages (excluding most recent for context window)
    if history:
        # Limit history to last 10 messages to control token usage
        for msg in history[-10:]:
            messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({"role": "user", "content": user_input})

    return messages

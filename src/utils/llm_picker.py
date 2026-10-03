"""LLM picker utility — select the right model for the right task."""
import os

from langchain_openai import ChatOpenAI

try:
    from langchain_anthropic import ChatAnthropic
    _HAS_ANTHROPIC = True
except ImportError:
    _HAS_ANTHROPIC = False


def pick_llm(level: str = "low"):
    """Return a LangChain chat LLM instance based on the desired capability level."""
    level = level.lower().strip()

    if level == "low":
        return ChatOpenAI(model=os.environ.get("LOW_MODEL", "gpt-4o-mini"), temperature=0)
    elif level == "medium":
        return ChatOpenAI(model=os.environ.get("MEDIUM_MODEL", "gpt-4o"), temperature=0)
    elif level == "high":
        return ChatOpenAI(model=os.environ.get("HIGH_MODEL", "gpt-4o"), temperature=0)
    elif level == "claude":
        if not _HAS_ANTHROPIC:
            raise ImportError("langchain-anthropic not installed")
        return ChatAnthropic(model=os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-5-20250514"))
    else:
        raise ValueError(f"Unknown LLM level: '{level}'. Use 'low', 'medium', 'high', or 'claude'.")

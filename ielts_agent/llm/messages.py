"""Lightweight chat message types.

These replace the handful of ``langchain_core.messages`` classes the agents
used, so the project doesn't pull in the (heavy) langchain stack just for three
data holders. The client (:mod:`ielts_agent.llm.client`) accepts these objects
or plain OpenAI-format dicts interchangeably.
"""

from __future__ import annotations


class ChatMessage:
    """Base chat message holding a role and text content."""

    role: str = "user"

    def __init__(self, content: str):
        self.content = content

    def to_api(self) -> dict:
        """Render to an OpenAI-compatible message dict."""
        return {"role": self.role, "content": str(self.content)}

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        preview = (self.content or "")[:40]
        return f"{self.__class__.__name__}({preview!r})"


class SystemMessage(ChatMessage):
    """A system instruction message."""

    role = "system"


class HumanMessage(ChatMessage):
    """A message from the user/student."""

    role = "user"


class AIMessage(ChatMessage):
    """A message from the assistant."""

    role = "assistant"

"""BigModel (智谱AI) GLM client — native SDK.

Targets GLM-5.1, which is a *hybrid reasoning* model: by default it emits a
``reasoning_content`` stream before the user-facing ``content``. We expose a
``thinking`` switch so interactive/streaming calls stay snappy (thinking off →
content streams immediately) while scoring can opt into deeper reasoning.

The client also speaks OpenAI-compatible tool calling, which powers the Coach
orchestrator. Messages may be :mod:`ielts_agent.llm.messages` objects or plain
OpenAI-format dicts (used for assistant tool-call turns and tool results).
"""

import json
import os
from typing import Any, Iterator, List, Optional, Union

from zhipuai import ZhipuAI

from ielts_agent.config import get_api_key, DEFAULT_MODEL, SCORING_MODEL
from ielts_agent.llm.messages import ChatMessage

# Disable proxy for all HTTP requests (corporate proxies break the SDK).
for _var in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
    os.environ.pop(_var, None)

# Global client instance for connection reuse.
_client: Optional[ZhipuAI] = None

MessageLike = Union[ChatMessage, dict]


def _get_client() -> ZhipuAI:
    """Get or create a shared ZhipuAI client."""
    global _client
    if _client is None:
        _client = ZhipuAI(api_key=get_api_key())
    return _client


class ToolCall:
    """A normalized tool call requested by the model."""

    def __init__(self, call_id: str, name: str, arguments: dict):
        self.id = call_id
        self.name = name
        self.arguments = arguments  # already-parsed JSON object

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"ToolCall({self.name}, {self.arguments})"


class LLMResponse:
    """A single non-streaming model response.

    ``.content`` keeps the historical attribute name agents relied on, so
    existing callers (``response.content``) keep working unchanged.
    """

    def __init__(
        self,
        content: Optional[str],
        reasoning_content: Optional[str] = None,
        tool_calls: Optional[List[ToolCall]] = None,
        finish_reason: Optional[str] = None,
    ):
        self.content = content or ""
        self.reasoning_content = reasoning_content
        self.tool_calls = tool_calls or []
        self.finish_reason = finish_reason


class SimpleLLM:
    """Thin wrapper over the ZhipuAI SDK with thinking + tool-calling support."""

    def __init__(self, model: str, temperature: float = 0.7, thinking: bool = False):
        self.model = model
        self.temperature = temperature
        self.thinking = thinking
        self.client = _get_client()

    @staticmethod
    def _prepare_messages(messages: List[MessageLike]) -> List[dict]:
        """Normalize messages to OpenAI-format dicts.

        Accepts our :class:`ChatMessage` objects (mapped by role — fixing the
        old bug where assistant turns were sent as ``system``) or raw dicts,
        which pass through untouched so tool-call/tool-result turns work.
        """
        api_messages: List[dict] = []
        for msg in messages:
            if isinstance(msg, dict):
                api_messages.append(msg)
            elif isinstance(msg, ChatMessage):
                api_messages.append(msg.to_api())
            elif hasattr(msg, "content"):
                # Defensive: tolerate langchain-style objects if ever passed.
                role = "user" if msg.__class__.__name__ == "HumanMessage" else (
                    "assistant" if msg.__class__.__name__ == "AIMessage" else "system"
                )
                api_messages.append({"role": role, "content": str(msg.content)})
            else:
                api_messages.append({"role": "user", "content": str(msg)})
        return api_messages

    def _extra_body(self) -> dict:
        """Toggle GLM-5.1's hybrid reasoning."""
        return {"thinking": {"type": "enabled" if self.thinking else "disabled"}}

    def invoke(
        self,
        messages: List[MessageLike],
        tools: Optional[List[dict]] = None,
        tool_choice: str = "auto",
    ) -> LLMResponse:
        """Non-streaming completion. Returns content, reasoning, and tool calls."""
        api_messages = self._prepare_messages(messages)
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": api_messages,
            "temperature": self.temperature,
            "timeout": 120.0,
            "extra_body": self._extra_body(),
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice

        try:
            response = self.client.chat.completions.create(**kwargs)
            message = response.choices[0].message
            tool_calls: List[ToolCall] = []
            for tc in (getattr(message, "tool_calls", None) or []):
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except (json.JSONDecodeError, TypeError):
                    args = {}
                tool_calls.append(ToolCall(tc.id, tc.function.name, args))
            return LLMResponse(
                content=message.content,
                reasoning_content=getattr(message, "reasoning_content", None),
                tool_calls=tool_calls,
                finish_reason=response.choices[0].finish_reason,
            )
        except Exception as exc:  # noqa: BLE001 - surface as a readable message
            return LLMResponse(content=f"Error generating response: {exc}")

    def stream(
        self,
        messages: List[MessageLike],
        include_reasoning: bool = False,
    ) -> Iterator[str]:
        """Stream content chunks. With thinking off, content arrives immediately.

        When ``include_reasoning`` is True, reasoning chunks are yielded too
        (callers that want a visible "thinking…" trace); otherwise only the
        final answer text is yielded.
        """
        api_messages = self._prepare_messages(messages)
        try:
            stream_response = self.client.chat.completions.create(
                model=self.model,
                messages=api_messages,
                temperature=self.temperature,
                timeout=120.0,
                stream=True,
                extra_body=self._extra_body(),
            )
            for chunk in stream_response:
                delta = chunk.choices[0].delta
                if include_reasoning and getattr(delta, "reasoning_content", None):
                    yield delta.reasoning_content
                if getattr(delta, "content", None):
                    yield delta.content
        except Exception as exc:  # noqa: BLE001
            yield f"\n\n[Error: {exc}]"


def get_llm(
    model: Optional[str] = None,
    temperature: float = 0.7,
    thinking: bool = False,
) -> SimpleLLM:
    """Get an LLM instance for interactive/generation tasks (thinking off)."""
    return SimpleLLM(model=model or DEFAULT_MODEL, temperature=temperature, thinking=thinking)


def get_llm_for_scoring(thinking: bool = True) -> SimpleLLM:
    """Get a scoring LLM: low temperature for consistency, reasoning on by default."""
    return SimpleLLM(model=SCORING_MODEL, temperature=0.3, thinking=thinking)

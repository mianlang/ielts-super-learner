"""BigModel (智谱AI) LLM client - native SDK for better performance."""

import os
from zhipuai import ZhipuAI
from ielts_agent.config import (
    get_api_key,
    DEFAULT_MODEL,
    ALTERNATIVE_MODEL,
)

# Disable proxy for all HTTP requests
os.environ.pop('HTTP_PROXY', None)
os.environ.pop('HTTPS_PROXY', None)
os.environ.pop('http_proxy', None)
os.environ.pop('https_proxy', None)
os.environ.pop('ALL_PROXY', None)
os.environ.pop('all_proxy', None)

# Global client instance for connection reuse
_client = None


def _get_client():
    """Get or create a shared ZhipuAI client."""
    global _client
    if _client is None:
        _client = ZhipuAI(api_key=get_api_key())
    return _client


class SimpleLLM:
    """Simple LLM wrapper for direct ZhipuAI SDK usage."""

    def __init__(self, model: str, temperature: float = 0.7):
        self.model = model
        self.temperature = temperature
        self.client = _get_client()

    def invoke(self, messages):
        """Invoke the LLM with messages."""
        # Convert LangChain messages to dict format
        api_messages = []
        for msg in messages:
            if hasattr(msg, 'content'):
                role = "user" if msg.__class__.__name__ == "HumanMessage" else "system"
                api_messages.append({"role": role, "content": str(msg.content)})
            else:
                api_messages.append({"role": "user", "content": str(msg)})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=api_messages,
            temperature=self.temperature,
        )

        return SimpleResponse(response.choices[0].message.content)


class SimpleResponse:
    """Simple response wrapper."""

    def __init__(self, content: str):
        self.content = content


def get_llm(model: str | None = None, temperature: float = 0.7) -> SimpleLLM:
    """
    Get an LLM instance configured for BigModel.

    Args:
        model: Model name (default: glm-4-flash)
        temperature: Sampling temperature (0.0 to 1.0)

    Returns:
        Configured LLM instance
    """
    if model is None:
        model = DEFAULT_MODEL
    return SimpleLLM(model=model, temperature=temperature)


def get_llm_for_scoring() -> SimpleLLM:
    """
    Get a higher-quality LLM instance for scoring tasks.

    Uses a lower temperature for more consistent scoring.

    Returns:
        Configured LLM instance for scoring
    """
    return SimpleLLM(model=ALTERNATIVE_MODEL, temperature=0.3)

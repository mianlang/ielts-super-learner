"""Tutor Agent - Conversational Q&A for IELTS concepts."""

from typing import Optional, List

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_openai import ChatOpenAI

from ielts_agent.llm.client import get_llm
from ielts_agent.prompts.ielts_prompts import (
    TUTOR_SYSTEM_PROMPT,
    PROACTIVE_TUTOR_SYSTEM_PROMPT,
    HARSH_TUTOR_SYSTEM_PROMPT,
)


class TutorAgent:
    """
    Conversational tutoring agent for IELTS learning.

    Provides answers to questions about:
    - IELTS test format and strategies
    - English grammar and vocabulary
    - Band score requirements
    - Study techniques and tips
    """

    def __init__(self, llm: Optional[ChatOpenAI] = None, proactive: bool = True, harsh: bool = False):
        """
        Initialize the tutor agent.

        Args:
            llm: Optional pre-configured LLM instance
            proactive: If True, use proactive tutor mode that drives conversation
            harsh: If True, use harsh drill instructor mode (authoritative, directive)
        """
        self.llm = llm or get_llm(temperature=0.7)
        self.proactive = proactive
        self.harsh = harsh
        self.system_prompt = self._select_system_prompt(proactive, harsh)
        self.conversation_history: List[tuple[str, str]] = []  # (user_message, assistant_message)

    def _select_system_prompt(self, proactive: bool, harsh: bool) -> str:
        """Select the appropriate system prompt based on mode."""
        if harsh:
            return HARSH_TUTOR_SYSTEM_PROMPT
        elif proactive:
            return PROACTIVE_TUTOR_SYSTEM_PROMPT
        else:
            return TUTOR_SYSTEM_PROMPT

    def ask(self, question: str) -> str:
        """
        Ask a question and get a response from the tutor.

        Args:
            question: The student's question

        Returns:
            The tutor's response
        """
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=question),
        ]

        response = self.llm.invoke(messages)
        return response.content

    def ask_proactive(self, question: str, follow_up: bool = True) -> str:
        """
        Ask a question with conversation history and get a proactive response.

        This method maintains conversation context and ensures the tutor
        always ends with a follow-up action or question.

        Args:
            question: The student's question or input
            follow_up: If True, ensure response ends with a proactive prompt

        Returns:
            The tutor's response with proactive follow-up
        """
        messages = [SystemMessage(content=self.system_prompt)]

        # Add conversation history
        for user_msg, assistant_msg in self.conversation_history:
            messages.append(HumanMessage(content=user_msg))
            messages.append(AIMessage(content=assistant_msg))

        # Add current question
        messages.append(HumanMessage(content=question))

        # Get response
        response = self.llm.invoke(messages)
        response_content = response.content

        # Store in history
        self.conversation_history.append((question, response_content))

        return response_content

    def ask_proactive_stream(self, question: str, follow_up: bool = True):
        """
        Stream a proactive response with conversation history.

        Yields content chunks as they arrive. Stores complete response in history.

        Args:
            question: The student's question or input
            follow_up: If True, ensure response ends with a proactive prompt

        Yields:
            str: Response content chunks
        """
        messages = [SystemMessage(content=self.system_prompt)]

        # Add conversation history
        for user_msg, assistant_msg in self.conversation_history:
            messages.append(HumanMessage(content=user_msg))
            messages.append(AIMessage(content=assistant_msg))

        # Add current question
        messages.append(HumanMessage(content=question))

        # Stream response and collect full content
        full_response = ""
        for chunk in self.llm.stream(messages):
            full_response += chunk
            yield chunk

        # Store in history
        self.conversation_history.append((question, full_response))

    def start_conversation(self) -> str:
        """
        Start a proactive conversation with an opening greeting.

        Returns:
            The tutor's opening message
        """
        if self.harsh:
            greeting_prompt = """Start the conversation. Command the student's attention immediately.
Demand their current level and target band score. Assign a first task.
Be brief, authoritative, and end with a directive."""
        else:
            greeting_prompt = """Start the conversation. Greet the student warmly and ask them about their IELTS goals.
Keep it brief and end with a specific question."""
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=greeting_prompt),
        ]

        response = self.llm.invoke(messages)
        response_content = response.content

        # Store in history (the "greeting" counts as a system-initiated exchange)
        self.conversation_history.append(("", response_content))

        return response_content

    def start_conversation_stream(self):
        """
        Stream a proactive conversation opening greeting.

        Yields:
            str: Greeting content chunks
        """
        if self.harsh:
            greeting_prompt = """Start the conversation. Command the student's attention immediately.
Demand their current level and target band score. Assign a first task.
Be brief, authoritative, and end with a directive."""
        else:
            greeting_prompt = """Start the conversation. Greet the student warmly and ask them about their IELTS goals.
Keep it brief and end with a specific question."""
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=greeting_prompt),
        ]

        # Stream response and collect full content
        full_response = ""
        for chunk in self.llm.stream(messages):
            full_response += chunk
            yield chunk

        # Store in history
        self.conversation_history.append(("", full_response))

    def reset_conversation(self) -> None:
        """Reset the conversation history."""
        self.conversation_history.clear()

    def set_proactive(self, proactive: bool) -> None:
        """
        Toggle proactive mode.

        Args:
            proactive: If True, use proactive system prompt
        """
        self.proactive = proactive
        self.system_prompt = self._select_system_prompt(proactive, self.harsh)

    def set_harsh(self, harsh: bool) -> None:
        """
        Toggle harsh mode.

        Args:
            harsh: If True, use harsh drill instructor prompt
        """
        self.harsh = harsh
        self.system_prompt = self._select_system_prompt(self.proactive, harsh)

    def ask_with_context(
        self, question: str, context: str, skill: Optional[str] = None
    ) -> str:
        """
        Ask a question with additional context.

        Args:
            question: The student's question
            context: Additional context to help answer the question
            skill: Optional IELTS skill focus (listening, reading, writing, speaking)

        Returns:
            The tutor's response
        """
        skill_hint = f"\nFocus area: {skill}" if skill else ""
        enhanced_prompt = f"""Context: {context}
{skill_hint}

Question: {question}"""

        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=enhanced_prompt),
        ]

        response = self.llm.invoke(messages)
        return response.content

    def explain_concept(self, concept: str, band_target: int = 7) -> str:
        """
        Get an explanation of an IELTS-related concept.

        Args:
            concept: The concept to explain (e.g., "coherence and cohesion")
            band_target: Target band score for context (default: 7)

        Returns:
            Detailed explanation of the concept
        """
        prompt = f"""Explain the concept of "{concept}" in the context of IELTS.
Aim your explanation at someone targeting Band {band_target}.
Include:
1. A clear definition
2. Why it matters for IELTS
3. Common mistakes
4. How to improve"""

        return self.ask(prompt)

    def get_tips(self, skill: str, band_target: int = 7) -> str:
        """
        Get tips for improving in a specific skill area.

        Args:
            skill: One of listening, reading, writing, speaking
            band_target: Target band score (default: 7)

        Returns:
            Practical tips for improvement
        """
        prompt = f"""Provide 5 specific, actionable tips for improving in IELTS {skill}
for someone targeting Band {band_target}.

Focus on practical strategies they can implement in their study routine.
Include specific exercises or techniques."""

        return self.ask(prompt)

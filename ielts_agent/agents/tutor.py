"""Tutor Agent - Conversational Q&A for IELTS concepts."""

from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from ielts_agent.llm.client import get_llm
from ielts_agent.prompts.ielts_prompts import TUTOR_SYSTEM_PROMPT


class TutorAgent:
    """
    Conversational tutoring agent for IELTS learning.

    Provides answers to questions about:
    - IELTS test format and strategies
    - English grammar and vocabulary
    - Band score requirements
    - Study techniques and tips
    """

    def __init__(self, llm: Optional[ChatOpenAI] = None):
        """
        Initialize the tutor agent.

        Args:
            llm: Optional pre-configured LLM instance
        """
        self.llm = llm or get_llm(temperature=0.7)
        self.system_prompt = TUTOR_SYSTEM_PROMPT

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

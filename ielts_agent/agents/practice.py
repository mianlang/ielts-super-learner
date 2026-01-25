"""Practice Agent - Generates IELTS practice questions."""

from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from ielts_agent.llm.client import get_llm
from ielts_agent.prompts.ielts_prompts import (
    PRACTICE_SYSTEM_PROMPT,
    WRITING_TASK_1_PROMPT_TEMPLATE,
    WRITING_TASK_2_PROMPT_TEMPLATE,
    SPEAKING_PART_1_PROMPT_TEMPLATE,
    SPEAKING_PART_2_PROMPT_TEMPLATE,
    SPEAKING_PART_3_PROMPT_TEMPLATE,
    READING_PROMPT_TEMPLATE,
    LISTENING_PROMPT_TEMPLATE,
)


class PracticeAgent:
    """
    Practice question generator for all IELTS skills.

    Generates authentic practice questions for:
    - Listening (all 4 sections)
    - Reading (academic passages with questions)
    - Writing Task 1 (graph/diagram/process/map)
    - Writing Task 2 (essay prompts)
    - Speaking Parts 1, 2, and 3
    """

    def __init__(self, llm: Optional[ChatOpenAI] = None):
        """
        Initialize the practice agent.

        Args:
            llm: Optional pre-configured LLM instance
        """
        self.llm = llm or get_llm(temperature=0.8)
        self.system_prompt = PRACTICE_SYSTEM_PROMPT

    def _generate(self, prompt: str) -> str:
        """Generate a practice question."""
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=prompt),
        ]
        response = self.llm.invoke(messages)
        return response.content

    def generate_listening(self, section: int = 1) -> str:
        """
        Generate a listening practice exercise.

        Args:
            section: Section number (1-4)

        Returns:
            Listening exercise with transcript and questions
        """
        section_descriptions = {
            1: "a conversation between two people in an everyday social context",
            2: "a monologue set in an everyday social context",
            3: "a conversation between up to four people in an educational or training context",
            4: "a monologue on an academic subject",
        }

        context = section_descriptions.get(section, section_descriptions[1])

        prompt = f"""Generate an IELTS Listening Section {section} practice exercise.

This section should feature {context}.

Include:
1. A brief description of the audio context (what the student would hear)
2. The transcript (200-300 words)
3. 5-6 questions in appropriate IELTS listening format
4. An answer key

Format the questions realistically as they would appear on the actual test."""

        return self._generate(prompt)

    def generate_reading(self, topic: Optional[str] = None) -> str:
        """
        Generate a reading practice passage with questions.

        Args:
            topic: Optional topic focus (e.g., "environment", "technology")

        Returns:
            Reading passage with comprehension questions
        """
        topic_hint = f" on the topic of {topic}" if topic else ""

        prompt = f"""Generate an IELTS Academic reading practice exercise{topic_hint}.

Include:
1. An authentic reading passage (700-800 words) with an academic tone
2. 6-8 comprehension questions using at least two different question types:
   - True/False/Not Given
   - Multiple choice
   - Matching headings
   - Sentence completion
   - Summary completion
3. An answer key with brief explanations

Make sure the passage and questions are at an authentic IELTS level (Band 6-8)."""

        return self._generate(prompt)

    def generate_writing_task1(self, task_type: Optional[str] = None) -> str:
        """
        Generate a Writing Task 1 practice question.

        Args:
            task_type: Type of visual (graph, chart, table, diagram, map, process)

        Returns:
            Task 1 question with visual description
        """
        if task_type:
            prompt = f"""Generate an IELTS Academic Writing Task 1 question
based on a {task_type}.

{WRITING_TASK_1_PROMPT_TEMPLATE}"""
        else:
            prompt = f"""Generate an IELTS Academic Writing Task 1 question.

Choose any appropriate visual type (line graph, bar chart, pie chart, table, process diagram, or map).

{WRITING_TASK_1_PROMPT_TEMPLATE}"""

        return self._generate(prompt)

    def generate_writing_task2(
        self, topic: Optional[str] = None, essay_type: Optional[str] = None
    ) -> str:
        """
        Generate a Writing Task 2 essay prompt.

        Args:
            topic: Optional topic area (e.g., "education", "technology")
            essay_type: Type (opinion, discussion, problem-solution, two-part, advantage-disadvantage)

        Returns:
            Task 2 essay prompt
        """
        topic_hint = f" related to {topic}" if topic else ""
        type_hint = f" This should be a {essay_type} essay." if essay_type else ""

        prompt = f"""Generate an IELTS Writing Task 2 essay prompt{topic_hint}.{type_hint}

{WRITING_TASK_2_PROMPT_TEMPLATE}"""

        return self._generate(prompt)

    def generate_speaking_part1(self, topic: Optional[str] = None) -> str:
        """
        Generate Speaking Part 1 questions.

        Args:
            topic: Optional topic area (e.g., "hometown", "hobbies")

        Returns:
            Set of Part 1 questions on one topic
        """
        topic_hint = f" on the topic of {topic}" if topic else " on a common Part 1 topic"

        prompt = f"""Generate IELTS Speaking Part 1 practice questions{topic_hint}.

{SPEAKING_PART_1_PROMPT_TEMPLATE}"""

        return self._generate(prompt)

    def generate_speaking_part2(self, topic: Optional[str] = None) -> str:
        """
        Generate a Speaking Part 2 task card.

        Args:
            topic: Optional topic theme

        Returns:
            Part 2 task card with bullet points
        """
        topic_hint = f" related to {topic}" if topic else ""

        prompt = f"""Generate an IELTS Speaking Part 2 task card{topic_hint}.

{SPEAKING_PART_2_PROMPT_TEMPLATE}"""

        return self._generate(prompt)

    def generate_speaking_part3(self, theme: Optional[str] = None) -> str:
        """
        Generate Speaking Part 3 discussion questions.

        Args:
            theme: Theme area for the discussion

        Returns:
            Set of Part 3 discussion questions
        """
        theme_hint = f" on the theme of {theme}" if theme else ""

        prompt = f"""Generate IELTS Speaking Part 3 discussion questions{theme_hint}.

{SPEAKING_PART_3_PROMPT_TEMPLATE}"""

        return self._generate(prompt)

    def generate_practice(self, skill: str, task: Optional[int] = None, **kwargs) -> str:
        """
        Generate a practice question based on skill and optional task.

        Args:
            skill: One of listening, reading, writing, speaking
            task: Task number (for writing/speaking)
            **kwargs: Additional parameters (topic, essay_type, etc.)

        Returns:
            Generated practice question
        """
        skill = skill.lower()

        if skill == "listening":
            section = kwargs.get("section", 1)
            return self.generate_listening(section)

        elif skill == "reading":
            topic = kwargs.get("topic")
            return self.generate_reading(topic)

        elif skill == "writing":
            if task == 1:
                task_type = kwargs.get("task_type")
                return self.generate_writing_task1(task_type)
            else:  # task 2 or default
                topic = kwargs.get("topic")
                essay_type = kwargs.get("essay_type")
                return self.generate_writing_task2(topic, essay_type)

        elif skill == "speaking":
            topic = kwargs.get("topic")
            if task == 1:
                return self.generate_speaking_part1(topic)
            elif task == 2:
                return self.generate_speaking_part2(topic)
            else:  # task 3 or default
                theme = kwargs.get("theme", topic)
                return self.generate_speaking_part3(theme)

        else:
            return f"Unknown skill: {skill}. Use listening, reading, writing, or speaking."

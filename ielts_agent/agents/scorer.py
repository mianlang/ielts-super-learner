"""Scorer Agent - Scores IELTS answers using official band descriptors."""

import json
import re
from typing import Optional, Dict, Any

from ielts_agent.llm.client import get_llm_for_scoring, SimpleLLM
from ielts_agent.llm.messages import HumanMessage, SystemMessage
from ielts_agent.prompts.ielts_prompts import (
    SCORING_SYSTEM_PROMPT,
    WRITING_BAND_DESCRIPTORS,
    SPEAKING_BAND_DESCRIPTORS,
)
from ielts_agent.config import WRITING_CRITERIA, SPEAKING_CRITERIA


class ScorerAgent:
    """
    Answer scoring agent using IELTS band descriptors.

    Scores written and spoken responses against official criteria.
    """

    def __init__(self, llm: Optional[SimpleLLM] = None):
        """
        Initialize the scorer agent.

        Args:
            llm: Optional pre-configured LLM instance
        """
        self.llm = llm or get_llm_for_scoring()
        self.scoring_prompt = SCORING_SYSTEM_PROMPT

    def _extract_band_score(self, response: str) -> float:
        """Extract the overall band score from the response."""
        # Try to find "Overall Band Score: X.X" pattern
        patterns = [
            r"Overall Band Score[:\s]+(\d+\.?\d*)",
            r"Overall Band[:\s]+(\d+\.?\d*)",
            r"Band Score[:\s]+(\d+\.?\d*)",
            r"Band[:\s]+(\d+\.?\d*)",
        ]

        for pattern in patterns:
            match = re.search(pattern, response, re.IGNORECASE)
            if match:
                score = float(match.group(1))
                return min(score, 9.0)  # Cap at 9.0

        # Fallback: try to find any number between 0-9 with decimal
        fallback_match = re.search(r"\b([0-8]\.[0-9]|9\.0)\b", response)
        if fallback_match:
            return float(fallback_match.group(1))

        return 0.0

    def score_writing(
        self,
        answer: str,
        task: int = 2,
        question: Optional[str] = None,
        prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Score a written response.

        Args:
            answer: The student's written response
            task: Task number (1 or 2)
            question: Optional question/prompt that was asked
            prompt: Optional full prompt text

        Returns:
            Dictionary with score and feedback
        """
        task_achievement = "Task Achievement" if task == 1 else "Task Response"

        scoring_prompt = f"""{self.scoring_prompt}

{WRITING_BAND_DESCRIPTORS}

You are scoring a Writing Task {task} response.

Assessment Criteria:
1. {task_achievement}
2. Coherence and Cohesion
3. Lexical Resource
4. Grammatical Range and Accuracy

{'Question/Prompt: ' + question if question else ''}
{'Full prompt: ' + prompt if prompt else ''}

Student Response:
{answer}

Please assess this response and provide:
1. An overall band score (0-9, can use .5 increments)
2. A breakdown by criterion
3. Specific strengths
4. Areas for improvement
5. Recommended actions"""

        messages = [
            SystemMessage(content=scoring_prompt),
            HumanMessage(content="Please score this response."),
        ]

        response = self.llm.invoke(messages)
        feedback = response.content
        overall_score = self._extract_band_score(feedback)

        return {
            "skill": "writing",
            "task": task,
            "overall_band_score": overall_score,
            "feedback": feedback,
            "criteria": WRITING_CRITERIA,
        }

    def score_speaking(
        self,
        answer: str,
        part: int = 2,
        question: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Score a spoken response.

        Args:
            answer: Transcription of the student's spoken response
            part: Speaking part (1, 2, or 3)
            question: Optional question that was asked

        Returns:
            Dictionary with score and feedback
        """
        scoring_prompt = f"""{self.scoring_prompt}

{SPEAKING_BAND_DESCRIPTORS}

You are scoring a Speaking Part {part} response.

Assessment Criteria:
1. Fluency and Coherence
2. Lexical Resource
3. Grammatical Range and Accuracy
4. Pronunciation (Note: You cannot assess actual pronunciation from text, so comment on likely pronunciation issues based on the content)

{'Question: ' + question if question else ''}

Student Response (transcript):
{answer}

Please assess this response and provide:
1. An overall band score (0-9, can use .5 increments)
2. A breakdown by criterion
3. Specific strengths
4. Areas for improvement
5. Recommended actions

Note on Pronunciation: Since this is a transcript, provide general guidance on pronunciation features that might be relevant to the content shown."""

        messages = [
            SystemMessage(content=scoring_prompt),
            HumanMessage(content="Please score this response."),
        ]

        response = self.llm.invoke(messages)
        feedback = response.content
        overall_score = self._extract_band_score(feedback)

        return {
            "skill": "speaking",
            "part": part,
            "overall_band_score": overall_score,
            "feedback": feedback,
            "criteria": SPEAKING_CRITERIA,
        }

    def score_reading(
        self,
        answers: Dict[str, str],
        correct_answers: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Score reading comprehension answers.

        Args:
            answers: Student's answers {question_number: answer}
            correct_answers: Answer key

        Returns:
            Dictionary with score and feedback
        """
        correct_count = 0
        total = len(correct_answers)
        results = {}

        for q_num, correct_answer in correct_answers.items():
            student_answer = answers.get(q_num, "")
            is_correct = str(student_answer).strip().lower() == str(correct_answer).strip().lower()
            if is_correct:
                correct_count += 1
            results[q_num] = {
                "student_answer": student_answer,
                "correct_answer": correct_answer,
                "is_correct": is_correct,
            }

        # IELTS Reading is scored out of 40, then converted to bands
        raw_score = correct_count
        band_score = self._reading_score_to_band(raw_score)

        return {
            "skill": "reading",
            "raw_score": raw_score,
            "total_questions": total,
            "band_score": band_score,
            "results": results,
        }

    def score_listening(
        self,
        answers: Dict[str, str],
        correct_answers: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Score listening answers.

        Args:
            answers: Student's answers {question_number: answer}
            correct_answers: Answer key

        Returns:
            Dictionary with score and feedback
        """
        correct_count = 0
        total = len(correct_answers)
        results = {}

        for q_num, correct_answer in correct_answers.items():
            student_answer = answers.get(q_num, "")
            is_correct = str(student_answer).strip().lower() == str(correct_answer).strip().lower()
            if is_correct:
                correct_count += 1
            results[q_num] = {
                "student_answer": student_answer,
                "correct_answer": correct_answer,
                "is_correct": is_correct,
            }

        # IELTS Listening is scored out of 40, then converted to bands
        raw_score = correct_count
        band_score = self._listening_score_to_band(raw_score)

        return {
            "skill": "listening",
            "raw_score": raw_score,
            "total_questions": total,
            "band_score": band_score,
            "results": results,
        }

    def _reading_score_to_band(self, raw_score: int) -> float:
        """Convert raw reading score (out of 40) to band score."""
        # Approximate IELTS reading score conversion
        if raw_score >= 39:
            return 9.0
        elif raw_score >= 37:
            return 8.5
        elif raw_score >= 35:
            return 8.0
        elif raw_score >= 33:
            return 7.5
        elif raw_score >= 30:
            return 7.0
        elif raw_score >= 27:
            return 6.5
        elif raw_score >= 23:
            return 6.0
        elif raw_score >= 19:
            return 5.5
        elif raw_score >= 15:
            return 5.0
        elif raw_score >= 13:
            return 4.5
        elif raw_score >= 10:
            return 4.0
        else:
            return max(3.0, raw_score / 3.0)

    def _listening_score_to_band(self, raw_score: int) -> float:
        """Convert raw listening score (out of 40) to band score."""
        # Approximate IELTS listening score conversion
        if raw_score >= 39:
            return 9.0
        elif raw_score >= 37:
            return 8.5
        elif raw_score >= 35:
            return 8.0
        elif raw_score >= 32:
            return 7.5
        elif raw_score >= 30:
            return 7.0
        elif raw_score >= 26:
            return 6.5
        elif raw_score >= 23:
            return 6.0
        elif raw_score >= 18:
            return 5.5
        elif raw_score >= 16:
            return 5.0
        elif raw_score >= 13:
            return 4.5
        elif raw_score >= 10:
            return 4.0
        else:
            return max(3.0, raw_score / 3.0)

    def score(self, skill: str, answer: str, **kwargs) -> Dict[str, Any]:
        """
        Score an answer based on skill.

        Args:
            skill: One of writing, speaking, reading, listening
            answer: The student's response
            **kwargs: Additional parameters (task, question, etc.)

        Returns:
            Dictionary with score and feedback
        """
        skill = skill.lower()

        if skill == "writing":
            task = kwargs.get("task", 2)
            question = kwargs.get("question")
            prompt = kwargs.get("prompt")
            return self.score_writing(answer, task, question, prompt)

        elif skill == "speaking":
            part = kwargs.get("part", 2)
            question = kwargs.get("question")
            return self.score_speaking(answer, part, question)

        elif skill in ("reading", "listening"):
            # For reading/listening, we need correct answers
            correct_answers = kwargs.get("correct_answers", {})
            if skill == "reading":
                return self.score_reading(answer, correct_answers)
            else:
                return self.score_listening(answer, correct_answers)

        else:
            return {"error": f"Unknown skill: {skill}"}

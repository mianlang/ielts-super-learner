"""Coach Agent — the orchestrator.

The Tutor is no longer a scripted chatbot. It runs a tool-calling loop on
GLM-5.1: it diagnoses the student, then drives a coaching cycle by calling
Practice (generate a question), Scorer (band a real answer), and a profile
updater (remember what it learns). All of it is anchored to a persisted
:class:`~ielts_agent.profile.LearnerProfile`, which is injected into the system
prompt every turn so coaching stays continuous across messages and sessions.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional, Tuple

from ielts_agent.agents.practice import PracticeAgent
from ielts_agent.agents.scorer import ScorerAgent
from ielts_agent.llm.client import get_llm, SimpleLLM
from ielts_agent.profile import LearnerProfile
from ielts_agent.prompts.ielts_prompts import (
    COACH_SYSTEM_PROMPT,
    HARSH_COACH_SYSTEM_PROMPT,
)

# --------------------------------------------------------------------------- #
# Tool schemas exposed to the model (OpenAI-compatible function calling).
# --------------------------------------------------------------------------- #
COACH_TOOLS: List[dict] = [
    {
        "type": "function",
        "function": {
            "name": "update_learner_profile",
            "description": (
                "Save durable facts about the student so coaching stays "
                "personalised across turns and sessions. Call this whenever you "
                "learn the student's band, target, exam date, weaknesses, "
                "strengths, or focus skill."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "current_band": {
                        "type": "number",
                        "description": "Estimated current overall band (0-9, .5 steps).",
                    },
                    "target_band": {
                        "type": "number",
                        "description": "Band the student is aiming for.",
                    },
                    "exam_date": {
                        "type": "string",
                        "description": "Exam date as YYYY-MM-DD.",
                    },
                    "focus_skill": {
                        "type": "string",
                        "enum": ["writing", "speaking", "reading", "listening"],
                    },
                    "add_weaknesses": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Concrete weaknesses to add, e.g. 'task response', 'grammatical range'.",
                    },
                    "add_strengths": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "notes": {
                        "type": "string",
                        "description": "Short freeform coaching note to remember.",
                    },
                    "mark_diagnostic_done": {
                        "type": "boolean",
                        "description": "Set true once the first-contact diagnostic is complete.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_practice_question",
            "description": "Generate a real IELTS practice question/task for the student to attempt.",
            "parameters": {
                "type": "object",
                "properties": {
                    "skill": {
                        "type": "string",
                        "enum": ["writing", "speaking", "reading", "listening"],
                    },
                    "task": {
                        "type": "integer",
                        "description": (
                            "Writing task 1/2; Speaking part 1/2/3; Listening section 1-4. "
                            "Omit for reading."
                        ),
                    },
                    "topic": {
                        "type": "string",
                        "description": "Optional topic focus (e.g. 'technology', 'environment').",
                    },
                },
                "required": ["skill"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "score_answer",
            "description": (
                "Score a student's written or spoken answer against IELTS band "
                "descriptors. Writing and speaking only. Returns a band score and "
                "detailed feedback, and auto-logs the score to the profile."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "skill": {"type": "string", "enum": ["writing", "speaking"]},
                    "task": {
                        "type": "integer",
                        "description": "Writing task 1/2 or speaking part 1/2/3.",
                    },
                    "question": {
                        "type": "string",
                        "description": "The prompt the answer responds to (use the last generated question if applicable).",
                    },
                    "answer": {
                        "type": "string",
                        "description": "The student's full answer text.",
                    },
                },
                "required": ["skill", "answer"],
            },
        },
    },
]

# Friendly labels for UI status while a tool runs.
TOOL_LABELS = {
    "update_learner_profile": "🧠 Updating your profile…",
    "generate_practice_question": "✍️ Generating a practice question…",
    "score_answer": "📊 Scoring your answer…",
}


def tool_label(name: str) -> str:
    """Human-readable status string for a tool call."""
    return TOOL_LABELS.get(name, f"Running {name}…")


# Type alias for the optional UI status callback: on_event(kind, data).
EventCallback = Optional[Callable[[str, Dict[str, Any]], None]]


class TutorAgent:
    """Coaching orchestrator backed by a persisted learner profile."""

    MAX_STEPS = 6  # safety bound on tool-call iterations per turn

    def __init__(
        self,
        profile: Optional[LearnerProfile] = None,
        harsh: bool = False,
        llm: Optional[SimpleLLM] = None,
        # Back-compat: old callers passed proactive=...; accept and ignore it.
        proactive: bool = True,
    ):
        self.profile = profile or LearnerProfile()
        self.harsh = harsh
        # Orchestration runs with thinking off for snappy turns; the nested
        # Scorer enables reasoning on its own for quality band judgments.
        self.llm = llm or get_llm(temperature=0.6, thinking=False)
        self.practice = PracticeAgent()
        self.scorer = ScorerAgent()
        self.history: List[dict] = []  # OpenAI-format user/assistant turns
        self.last_question: Optional[str] = None
        self.profile_dirty = False

    # ------------------------------------------------------------------ config
    def set_harsh(self, harsh: bool) -> None:
        self.harsh = harsh

    def reset_conversation(self) -> None:
        """Clear the chat transcript but keep the (persistent) profile."""
        self.history.clear()
        self.last_question = None

    def _system_prompt(self) -> str:
        base = HARSH_COACH_SYSTEM_PROMPT if self.harsh else COACH_SYSTEM_PROMPT
        return f"{base}\n\n{self.profile.summary_for_prompt()}"

    # -------------------------------------------------------------- tool layer
    def _dispatch_tool(self, name: str, args: dict) -> str:
        try:
            if name == "update_learner_profile":
                return self._tool_update_profile(args)
            if name == "generate_practice_question":
                return self._tool_generate(args)
            if name == "score_answer":
                return self._tool_score(args)
            return f"Unknown tool: {name}"
        except Exception as exc:  # noqa: BLE001 - report to the model, don't crash
            return f"Tool '{name}' failed: {exc}"

    def _tool_update_profile(self, args: dict) -> str:
        p = self.profile
        changed: List[str] = []
        if args.get("current_band") is not None:
            p.current_band = float(args["current_band"])
            changed.append("current_band")
        if args.get("target_band") is not None:
            p.target_band = float(args["target_band"])
            changed.append("target_band")
        if args.get("exam_date"):
            p.exam_date = str(args["exam_date"])
            changed.append("exam_date")
        if args.get("focus_skill"):
            p.focus_skill = str(args["focus_skill"]).lower()
            changed.append("focus_skill")
        if args.get("add_weaknesses"):
            p.add_weaknesses(list(args["add_weaknesses"]))
            changed.append("weaknesses")
        if args.get("add_strengths"):
            p.add_strengths(list(args["add_strengths"]))
            changed.append("strengths")
        if args.get("notes"):
            p.notes = str(args["notes"])
            changed.append("notes")
        if args.get("mark_diagnostic_done"):
            p.diagnostic_done = True
            changed.append("diagnostic_done")
        p.touch()
        self.profile_dirty = True
        what = ", ".join(changed) if changed else "nothing"
        return f"Profile updated ({what}).\n\n{p.summary_for_prompt()}"

    def _tool_generate(self, args: dict) -> str:
        skill = str(args.get("skill", "writing")).lower()
        task = args.get("task")
        kwargs: Dict[str, Any] = {}
        if args.get("topic"):
            kwargs["topic"] = args["topic"]
        question = self.practice.generate_practice(skill, task=task, **kwargs)
        self.last_question = question
        return question

    def _tool_score(self, args: dict) -> str:
        skill = str(args.get("skill", "writing")).lower()
        if skill not in ("writing", "speaking"):
            return "Scoring is only available for writing and speaking."
        answer = str(args.get("answer", "")).strip()
        if not answer:
            return "No answer text was provided to score."
        task = args.get("task")
        question = args.get("question") or self.last_question

        score_kwargs: Dict[str, Any] = {}
        if question:
            score_kwargs["question"] = question
        if skill == "writing":
            score_kwargs["task"] = task or 2
        else:
            score_kwargs["part"] = task or 2

        result = self.scorer.score(skill, answer, **score_kwargs)
        band = result.get("overall_band_score") or result.get("band_score") or 0
        self.profile.add_score(skill, task, float(band), summary=(question or "")[:80])
        self.profile_dirty = True
        feedback = result.get("feedback", "")
        return f"Band score: {band}\n\n{feedback}"

    # ----------------------------------------------------------- orchestration
    def _run(self, seed_messages: List[dict], on_event: EventCallback) -> Tuple[str, List[dict]]:
        """Run the tool-calling loop and return (final_text, tool_events)."""
        messages: List[dict] = (
            [{"role": "system", "content": self._system_prompt()}]
            + self.history
            + seed_messages
        )
        events: List[dict] = []

        for _ in range(self.MAX_STEPS):
            resp = self.llm.invoke(messages, tools=COACH_TOOLS)
            if not resp.tool_calls:
                return resp.content or "", events

            # Echo the assistant's tool-call turn back into the transcript.
            messages.append(
                {
                    "role": "assistant",
                    "content": resp.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments),
                            },
                        }
                        for tc in resp.tool_calls
                    ],
                }
            )
            for tc in resp.tool_calls:
                if on_event:
                    on_event("tool_start", {"name": tc.name, "args": tc.arguments})
                result = self._dispatch_tool(tc.name, tc.arguments)
                events.append({"name": tc.name, "args": tc.arguments, "result": result})
                messages.append(
                    {"role": "tool", "tool_call_id": tc.id, "content": result}
                )
                if on_event:
                    on_event("tool_end", {"name": tc.name})

        # Exhausted the step budget — ask for a wrap-up with no further tools.
        wrap = self.llm.invoke(messages)
        return (wrap.content or "Let's keep going — what would you like to work on next?"), events

    def chat(self, user_input: str, on_event: EventCallback = None) -> Dict[str, Any]:
        """Process one student message through the coaching loop."""
        self.profile_dirty = False
        user_msg = {"role": "user", "content": user_input}
        final, events = self._run([user_msg], on_event)
        self.history.append(user_msg)
        self.history.append({"role": "assistant", "content": final})
        self._trim_history()
        return {"content": final, "events": events, "profile_changed": self.profile_dirty}

    def start(self, on_event: EventCallback = None) -> Dict[str, Any]:
        """Open the session: greet, then diagnose or welcome back per the profile."""
        self.profile_dirty = False
        opening = (
            "[SESSION START] The student just opened the app. Greet them and begin "
            "according to your instructions: if the diagnostic is not done, run the "
            "first-contact diagnostic; otherwise welcome them back and propose the "
            "next drill based on their profile."
        )
        final, events = self._run([{"role": "user", "content": opening}], on_event)
        # Store only the assistant greeting; the synthetic opening stays hidden.
        self.history.append({"role": "assistant", "content": final})
        self._trim_history()
        return {"content": final, "events": events, "profile_changed": self.profile_dirty}

    def _trim_history(self, max_messages: int = 24) -> None:
        if len(self.history) > max_messages:
            self.history = self.history[-max_messages:]

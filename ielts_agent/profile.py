"""Learner profile — the persisted state that turns chat into coaching.

The profile is a plain dataclass with JSON (de)serialization so it can live
anywhere: SQLite for the CLI, browser localStorage for the Streamlit app, or
session memory as a fallback. It also renders a compact text summary that gets
injected into the Coach's system prompt each turn, which is how the Coach
"remembers" the student across messages and across sessions.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional

# Canonical IELTS writing/speaking weakness tags the Coach tends to use. Free
# text is also allowed; this list just documents the common vocabulary.
COMMON_WEAKNESSES = [
    "task response",
    "task achievement",
    "coherence and cohesion",
    "lexical resource",
    "grammatical range and accuracy",
    "fluency",
    "pronunciation",
    "paragraphing",
    "overview / main trends",
    "complex sentences",
    "word choice / collocation",
]


@dataclass
class ScoreRecord:
    """One scored attempt, kept for trend tracking."""

    date: str
    skill: str
    task: Optional[int]
    band: float
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "skill": self.skill,
            "task": self.task,
            "band": self.band,
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ScoreRecord":
        return cls(
            date=d.get("date", ""),
            skill=d.get("skill", ""),
            task=d.get("task"),
            band=float(d.get("band", 0) or 0),
            summary=d.get("summary", ""),
        )


@dataclass
class LearnerProfile:
    """Everything the Coach knows about one student."""

    name: str = "Student"
    current_band: Optional[float] = None
    target_band: Optional[float] = None
    exam_date: Optional[str] = None  # ISO date string, e.g. "2026-08-01"
    focus_skill: str = "writing"
    weaknesses: List[str] = field(default_factory=list)
    strengths: List[str] = field(default_factory=list)
    diagnostic_done: bool = False
    notes: str = ""
    score_history: List[ScoreRecord] = field(default_factory=list)
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # ---------------------------------------------------------------- mutation
    def touch(self) -> None:
        self.updated_at = datetime.now().isoformat()

    def add_score(self, skill: str, task: Optional[int], band: float, summary: str = "") -> None:
        """Record a scored attempt and refresh the current-band estimate."""
        self.score_history.append(
            ScoreRecord(
                date=datetime.now().strftime("%Y-%m-%d"),
                skill=skill,
                task=task,
                band=round(float(band), 1),
                summary=summary,
            )
        )
        # Keep only the most recent 30 records to stay localStorage-friendly.
        self.score_history = self.score_history[-30:]
        self.touch()

    def add_weaknesses(self, items: List[str]) -> None:
        for raw in items:
            tag = raw.strip().lower()
            if tag and tag not in self.weaknesses:
                self.weaknesses.append(tag)
        self.touch()

    def add_strengths(self, items: List[str]) -> None:
        for raw in items:
            tag = raw.strip().lower()
            if tag and tag not in self.strengths:
                self.strengths.append(tag)
        self.touch()

    # ----------------------------------------------------------------- derived
    def days_until_exam(self) -> Optional[int]:
        if not self.exam_date:
            return None
        try:
            exam = date.fromisoformat(self.exam_date)
        except ValueError:
            return None
        return (exam - date.today()).days

    def band_gap(self) -> Optional[float]:
        if self.current_band is None or self.target_band is None:
            return None
        return round(self.target_band - self.current_band, 1)

    def latest_band(self, skill: Optional[str] = None) -> Optional[float]:
        records = [r for r in self.score_history if skill is None or r.skill == skill]
        return records[-1].band if records else None

    def summary_for_prompt(self) -> str:
        """Compact context block injected into the Coach's system prompt."""
        if self._is_blank():
            return (
                "LEARNER PROFILE: empty. This is a brand-new student — you have no "
                "information yet. Run the first-contact diagnostic before drilling."
            )

        lines = ["LEARNER PROFILE (use this to personalise every turn):"]
        lines.append(f"- Name: {self.name}")
        if self.current_band is not None or self.target_band is not None:
            cur = self.current_band if self.current_band is not None else "unknown"
            tgt = self.target_band if self.target_band is not None else "unknown"
            gap = self.band_gap()
            gap_txt = f" (gap {gap:+.1f})" if gap is not None else ""
            lines.append(f"- Current band: {cur} | Target: {tgt}{gap_txt}")
        days = self.days_until_exam()
        if self.exam_date:
            when = f"{self.exam_date}"
            if days is not None:
                when += f" ({days} days away)" if days >= 0 else " (date has passed)"
            lines.append(f"- Exam date: {when}")
        lines.append(f"- Focus skill: {self.focus_skill}")
        if self.weaknesses:
            lines.append(f"- Weaknesses to drill: {', '.join(self.weaknesses)}")
        if self.strengths:
            lines.append(f"- Strengths: {', '.join(self.strengths)}")
        lines.append(f"- Diagnostic completed: {'yes' if self.diagnostic_done else 'no'}")
        if self.score_history:
            recent = self.score_history[-5:]
            rendered = "; ".join(
                f"{r.skill.capitalize()}"
                + (f" T{r.task}" if r.task else "")
                + f" {r.band} ({r.date})"
                for r in recent
            )
            lines.append(f"- Recent scores: {rendered}")
        if self.notes:
            lines.append(f"- Coach notes: {self.notes}")
        return "\n".join(lines)

    def _is_blank(self) -> bool:
        return (
            not self.diagnostic_done
            and self.current_band is None
            and self.target_band is None
            and not self.weaknesses
            and not self.score_history
        )

    # ----------------------------------------------------------- serialization
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "current_band": self.current_band,
            "target_band": self.target_band,
            "exam_date": self.exam_date,
            "focus_skill": self.focus_skill,
            "weaknesses": self.weaknesses,
            "strengths": self.strengths,
            "diagnostic_done": self.diagnostic_done,
            "notes": self.notes,
            "score_history": [r.to_dict() for r in self.score_history],
            "updated_at": self.updated_at,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, d: dict) -> "LearnerProfile":
        return cls(
            name=d.get("name", "Student"),
            current_band=d.get("current_band"),
            target_band=d.get("target_band"),
            exam_date=d.get("exam_date"),
            focus_skill=d.get("focus_skill", "writing"),
            weaknesses=list(d.get("weaknesses", [])),
            strengths=list(d.get("strengths", [])),
            diagnostic_done=bool(d.get("diagnostic_done", False)),
            notes=d.get("notes", ""),
            score_history=[ScoreRecord.from_dict(r) for r in d.get("score_history", [])],
            updated_at=d.get("updated_at", datetime.now().isoformat()),
        )

    @classmethod
    def from_json(cls, raw: Optional[str]) -> "LearnerProfile":
        if not raw:
            return cls()
        try:
            return cls.from_dict(json.loads(raw))
        except (json.JSONDecodeError, TypeError, ValueError):
            return cls()

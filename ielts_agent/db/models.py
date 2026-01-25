"""Data models for IELTS Agent database."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class User:
    """User model representing a learner."""

    id: int
    name: str
    created_at: datetime

    @classmethod
    def create(cls, name: str) -> "User":
        """Create a new user (for insertion)."""
        return cls(
            id=0,  # Will be set by database
            name=name,
            created_at=datetime.now(),
        )


@dataclass
class Session:
    """Practice session model."""

    id: int
    user_id: int
    skill: str  # listening, reading, writing, speaking
    task: Optional[int]  # 1 or 2 for writing/speaking parts
    started_at: datetime
    ended_at: Optional[datetime] = None

    @classmethod
    def create(cls, user_id: int, skill: str, task: Optional[int] = None) -> "Session":
        """Create a new session."""
        return cls(
            id=0,
            user_id=user_id,
            skill=skill,
            task=task,
            started_at=datetime.now(),
            ended_at=None,
        )


@dataclass
class Interaction:
    """Interaction within a session."""

    id: int
    session_id: int
    interaction_type: str  # question, answer, score, feedback
    content: str
    timestamp: datetime
    metadata: Optional[str] = None  # JSON string for additional data

    @classmethod
    def create(
        cls,
        session_id: int,
        interaction_type: str,
        content: str,
        metadata: Optional[str] = None,
    ) -> "Interaction":
        """Create a new interaction."""
        return cls(
            id=0,
            session_id=session_id,
            interaction_type=interaction_type,
            content=content,
            timestamp=datetime.now(),
            metadata=metadata,
        )


@dataclass
class Progress:
    """Progress tracking per skill."""

    user_id: int
    skill: str
    practice_count: int
    avg_score: float
    last_practiced: datetime
    best_score: float = 0.0

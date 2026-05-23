"""Database schema and operations for IELTS Agent."""

import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

from ielts_agent.config import DB_PATH
from ielts_agent.db.models import User, Session, Interaction, Progress


def _get_connection() -> sqlite3.Connection:
    """Get a database connection."""
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initialize the database schema."""
    conn = _get_connection()
    cursor = conn.cursor()

    # Users table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # Sessions table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            skill TEXT NOT NULL,
            task INTEGER,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ended_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """
    )

    # Interactions table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            interaction_type TEXT NOT NULL CHECK(interaction_type IN ('question', 'answer', 'score', 'feedback')),
            content TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            metadata TEXT,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        )
    """
    )

    # Progress table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS progress (
            user_id INTEGER NOT NULL,
            skill TEXT NOT NULL,
            practice_count INTEGER DEFAULT 0,
            avg_score REAL DEFAULT 0.0,
            best_score REAL DEFAULT 0.0,
            last_practiced TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, skill),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """
    )

    # Learner profile table (one JSON blob per user — the Coach's memory).
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS profiles (
            user_id INTEGER PRIMARY KEY,
            data TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """
    )

    conn.commit()
    conn.close()


def get_or_create_user(name: str = "Student") -> User:
    """Get existing user or create a new one."""
    conn = _get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, name, created_at FROM users WHERE name = ?", (name,))
    row = cursor.fetchone()

    if row:
        conn.close()
        return User(id=row[0], name=row[1], created_at=datetime.fromisoformat(row[2]))

    # Create new user
    cursor.execute(
        "INSERT INTO users (name, created_at) VALUES (?, ?)",
        (name, datetime.now().isoformat()),
    )
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()

    return User(id=user_id, name=name, created_at=datetime.now())


def create_session(user_id: int, skill: str, task: Optional[int] = None) -> Session:
    """Create a new practice session."""
    conn = _get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO sessions (user_id, skill, task, started_at)
        VALUES (?, ?, ?, ?)
        """,
        (user_id, skill, task, datetime.now().isoformat()),
    )
    conn.commit()
    session_id = cursor.lastrowid
    conn.close()

    return Session(
        id=session_id,
        user_id=user_id,
        skill=skill,
        task=task,
        started_at=datetime.now(),
        ended_at=None,
    )


def end_session(session_id: int) -> None:
    """Mark a session as ended."""
    conn = _get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE sessions SET ended_at = ? WHERE id = ?",
        (datetime.now().isoformat(), session_id),
    )
    conn.commit()
    conn.close()


def save_interaction(
    session_id: int,
    interaction_type: str,
    content: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> int:
    """Save an interaction to the database."""
    conn = _get_connection()
    cursor = conn.cursor()

    metadata_json = json.dumps(metadata) if metadata else None

    cursor.execute(
        """
        INSERT INTO interactions (session_id, interaction_type, content, timestamp, metadata)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            session_id,
            interaction_type,
            content,
            datetime.now().isoformat(),
            metadata_json,
        ),
    )
    conn.commit()
    interaction_id = cursor.lastrowid
    conn.close()

    return interaction_id


def update_progress(
    user_id: int, skill: str, score: Optional[float] = None
) -> None:
    """Update progress tracking for a user and skill."""
    conn = _get_connection()
    cursor = conn.cursor()

    # Check if progress record exists
    cursor.execute(
        "SELECT practice_count, avg_score, best_score FROM progress WHERE user_id = ? AND skill = ?",
        (user_id, skill),
    )
    row = cursor.fetchone()

    if row:
        practice_count = row[0] + 1
        current_avg = row[1]
        best_score = row[2]

        # Update average score
        if score is not None:
            new_avg = ((current_avg * row[0]) + score) / practice_count
            best_score = max(best_score, score)
        else:
            new_avg = current_avg

        cursor.execute(
            """
            UPDATE progress
            SET practice_count = ?, avg_score = ?, best_score = ?, last_practiced = ?
            WHERE user_id = ? AND skill = ?
            """,
            (practice_count, new_avg, best_score, datetime.now().isoformat(), user_id, skill),
        )
    else:
        # Create new progress record
        avg_score = score if score is not None else 0.0
        best_score = score if score is not None else 0.0

        cursor.execute(
            """
            INSERT INTO progress (user_id, skill, practice_count, avg_score, best_score, last_practiced)
            VALUES (?, ?, 1, ?, ?, ?)
            """,
            (user_id, skill, avg_score, best_score, datetime.now().isoformat()),
        )

    conn.commit()
    conn.close()


def get_progress(user_id: int) -> List[Progress]:
    """Get progress for all skills."""
    conn = _get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT user_id, skill, practice_count, avg_score, best_score, last_practiced
        FROM progress WHERE user_id = ?
        ORDER BY skill
        """,
        (user_id,),
    )

    progress_list = []
    for row in cursor.fetchall():
        progress_list.append(
            Progress(
                user_id=row[0],
                skill=row[1],
                practice_count=row[2],
                avg_score=row[3],
                best_score=row[4],
                last_practiced=datetime.fromisoformat(row[5]),
            )
        )

    conn.close()
    return progress_list


def get_user_stats(user_id: int) -> Dict[str, Any]:
    """Get overall user statistics."""
    conn = _get_connection()
    cursor = conn.cursor()

    # Total sessions
    cursor.execute(
        "SELECT COUNT(*) FROM sessions WHERE user_id = ?", (user_id,)
    )
    total_sessions = cursor.fetchone()[0]

    # Total interactions
    cursor.execute(
        """
        SELECT COUNT(*) FROM interactions
        JOIN sessions ON interactions.session_id = sessions.id
        WHERE sessions.user_id = ?
        """,
        (user_id,),
    )
    total_interactions = cursor.fetchone()[0]

    # Last activity
    cursor.execute(
        """
        SELECT MAX(interactions.timestamp)
        FROM interactions
        JOIN sessions ON interactions.session_id = sessions.id
        WHERE sessions.user_id = ?
        """,
        (user_id,),
    )
    last_activity = cursor.fetchone()[0]

    # Average score across all skills
    cursor.execute(
        "SELECT AVG(avg_score) FROM progress WHERE user_id = ? AND avg_score > 0",
        (user_id,),
    )
    overall_avg = cursor.fetchone()[0] or 0.0

    conn.close()

    return {
        "total_sessions": total_sessions,
        "total_interactions": total_interactions,
        "last_activity": datetime.fromisoformat(last_activity) if last_activity else None,
        "overall_average_score": round(overall_avg, 2),
    }


def get_recent_sessions(user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """Get recent practice sessions."""
    conn = _get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT sessions.id, sessions.skill, sessions.task, sessions.started_at, sessions.ended_at,
               COUNT(interactions.id) as interaction_count
        FROM sessions
        LEFT JOIN interactions ON sessions.id = interactions.session_id
        WHERE sessions.user_id = ?
        GROUP BY sessions.id
        ORDER BY sessions.started_at DESC
        LIMIT ?
        """,
        (user_id, limit),
    )

    sessions = []
    for row in cursor.fetchall():
        sessions.append(
            {
                "id": row[0],
                "skill": row[1],
                "task": row[2],
                "started_at": datetime.fromisoformat(row[3]),
                "ended_at": datetime.fromisoformat(row[4]) if row[4] else None,
                "interaction_count": row[5],
            }
        )

    conn.close()
    return sessions


def get_profile_data(user_id: int) -> Optional[str]:
    """Return the stored learner-profile JSON blob for a user, if any."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT data FROM profiles WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


def save_profile_data(user_id: int, data: str) -> None:
    """Upsert a learner-profile JSON blob for a user."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO profiles (user_id, data, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at
        """,
        (user_id, data, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()

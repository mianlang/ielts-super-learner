"""Database module for IELTS Agent."""

from .schema import (
    init_db,
    save_interaction,
    get_progress,
    get_user_stats,
    get_or_create_user,
    create_session,
    end_session,
    update_progress,
    get_recent_sessions,
)
from .models import User, Session, Interaction, Progress

__all__ = [
    "init_db",
    "save_interaction",
    "get_progress",
    "get_user_stats",
    "get_or_create_user",
    "create_session",
    "end_session",
    "update_progress",
    "get_recent_sessions",
    "User",
    "Session",
    "Interaction",
    "Progress",
]

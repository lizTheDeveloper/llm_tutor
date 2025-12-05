"""
Database models package.
Contains SQLAlchemy ORM models for all database tables.
"""
from src.models.base import Base, get_db_session, init_db, close_db

# Import all models to ensure they're registered with SQLAlchemy
from src.models.user import User, UserRole, SkillLevel
from src.models.exercise import Exercise, UserExercise, ExerciseType, ExerciseDifficulty, ExerciseStatus
from src.models.conversation import Conversation, Message, MessageRole
from src.models.user_memory import UserMemory
from src.models.achievement import Achievement, UserAchievement, AchievementCategory
from src.models.interaction_log import InteractionLog

__all__ = [
    "Base",
    "get_db_session",
    "init_db",
    "close_db",
    "User",
    "UserRole",
    "SkillLevel",
    "Exercise",
    "UserExercise",
    "ExerciseType",
    "ExerciseDifficulty",
    "ExerciseStatus",
    "Conversation",
    "Message",
    "MessageRole",
    "UserMemory",
    "Achievement",
    "UserAchievement",
    "AchievementCategory",
    "InteractionLog",
]

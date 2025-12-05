"""
User model for authentication and profile management.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    String,
    Boolean,
    DateTime,
    Integer,
    Text,
    Enum as SQLEnum,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
import enum
from src.models.base import Base


class UserRole(str, enum.Enum):
    """User role enumeration."""
    STUDENT = "student"
    MENTOR = "mentor"
    MODERATOR = "moderator"
    ADMIN = "admin"


class SkillLevel(str, enum.Enum):
    """Skill level enumeration."""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class User(Base):
    """User model for authentication and profile."""

    __tablename__ = "users"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Authentication
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # OAuth
    github_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True, index=True)
    google_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True, index=True)
    oauth_provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Profile
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Preferences
    programming_language: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    skill_level: Mapped[Optional[SkillLevel]] = mapped_column(
        SQLEnum(SkillLevel, name="skill_level_enum"),
        nullable=True
    )
    career_goals: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    learning_style: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    time_commitment: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Role and status
    role: Mapped[UserRole] = mapped_column(
        SQLEnum(UserRole, name="user_role_enum"),
        default=UserRole.STUDENT,
        nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_mentor: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Progress tracking
    current_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    longest_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    exercises_completed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_exercise_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    # Onboarding
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        """String representation of User."""
        return f"<User(id={self.id}, email='{self.email}', role='{self.role}')>"

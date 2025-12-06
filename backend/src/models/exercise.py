"""
Exercise and User Exercise database models.
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
    ForeignKey,
    Float,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
import enum
from src.models.base import Base


class ExerciseType(str, enum.Enum):
    """Exercise type enumeration."""
    ALGORITHM = "algorithm"
    DATA_STRUCTURE = "data_structure"
    DEBUGGING = "debugging"
    PRACTICAL = "practical"


class ExerciseDifficulty(str, enum.Enum):
    """Exercise difficulty enumeration."""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class ExerciseStatus(str, enum.Enum):
    """User exercise completion status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"


class Exercise(Base):
    """
    Exercise model for storing coding exercises.
    """
    __tablename__ = "exercises"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Exercise content
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    instructions: Mapped[str] = mapped_column(Text, nullable=False)
    starter_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    solution: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Exercise metadata
    exercise_type: Mapped[ExerciseType] = mapped_column(
        SQLEnum(ExerciseType, name="exercise_type_enum"),
        nullable=False
    )
    difficulty: Mapped[ExerciseDifficulty] = mapped_column(
        SQLEnum(ExerciseDifficulty, name="exercise_difficulty_enum"),
        nullable=False,
        index=True  # DB-OPT: Index for adaptive difficulty algorithm
    )
    programming_language: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True  # DB-OPT: Index for language-based exercise generation
    )
    topics: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # Comma-separated

    # Test cases (stored as JSON string)
    test_cases: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # AI generation metadata
    generated_by_ai: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    generation_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    def __repr__(self) -> str:
        """String representation of Exercise."""
        return f"<Exercise(id={self.id}, title='{self.title}', difficulty='{self.difficulty}')>"


class UserExercise(Base):
    """
    User Exercise model for tracking user progress on exercises.
    """
    __tablename__ = "user_exercises"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign keys
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    exercise_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("exercises.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Status and completion
    status: Mapped[ExerciseStatus] = mapped_column(
        SQLEnum(ExerciseStatus, name="exercise_status_enum"),
        default=ExerciseStatus.PENDING,
        nullable=False,
        index=True  # DB-OPT: Index for progress tracking queries
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # User's work
    user_solution: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    hints_requested: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Grading and feedback
    grade: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # 0-100 scale
    ai_feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    mentor_feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Performance metrics
    time_spent_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    test_cases_passed: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    test_cases_total: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Timestamps
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    # DB-OPT: Add composite index for streak calculations and exercise history
    # Query: SELECT * FROM user_exercises WHERE user_id = X ORDER BY created_at DESC
    # This composite index optimizes both the filter and sort operations
    __table_args__ = (
        Index('idx_user_exercises_user_created', 'user_id', 'created_at'),
    )

    def __repr__(self) -> str:
        """String representation of UserExercise."""
        return f"<UserExercise(id={self.id}, user_id={self.user_id}, exercise_id={self.exercise_id}, status='{self.status}')>"

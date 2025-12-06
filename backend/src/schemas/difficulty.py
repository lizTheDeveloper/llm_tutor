"""
Pydantic schemas for difficulty adaptation system.

These schemas define the shape of data for:
- Performance metrics tracking
- Difficulty adjustment recommendations
- Difficulty change notifications
- API request/response formats
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field

from src.models.exercise import ExerciseDifficulty, ExerciseStatus


# ===================================================================
# PERFORMANCE TRACKING SCHEMAS
# ===================================================================

class ExercisePerformanceSummary(BaseModel):
    """Summary of a single exercise's performance metrics."""
    exercise_id: int
    difficulty: ExerciseDifficulty
    status: ExerciseStatus
    grade: Optional[float]
    hints_requested: int
    time_spent_seconds: Optional[int]
    completed_at: datetime
    is_success: bool = Field(description="Whether this counts as a successful completion")
    is_struggle: bool = Field(description="Whether this counts as a struggle")

    class Config:
        from_attributes = True
        orm_mode = True


class PerformanceMetrics(BaseModel):
    """
    Aggregated performance metrics for a user's recent exercises.
    Used to analyze performance patterns and determine difficulty adjustments.
    """
    user_id: int
    recent_exercises: List[ExercisePerformanceSummary] = Field(
        default_factory=list,
        description="List of recent exercise performances (most recent first)"
    )
    total_exercises_analyzed: int = Field(
        description="Total number of exercises included in analysis"
    )

    # Aggregated statistics
    average_grade: Optional[float] = Field(
        None,
        ge=0.0,
        le=100.0,
        description="Average grade across completed exercises"
    )
    average_hints: float = Field(
        ge=0.0,
        description="Average number of hints requested per exercise"
    )
    average_time_seconds: Optional[float] = Field(
        None,
        ge=0.0,
        description="Average time spent per exercise in seconds"
    )
    completion_rate: float = Field(
        ge=0.0,
        le=100.0,
        description="Percentage of exercises completed (not skipped)"
    )

    # Consecutive patterns (key for adaptation algorithm)
    consecutive_successes: int = Field(
        ge=0,
        description="Number of consecutive successful exercises without hints"
    )
    consecutive_struggles: int = Field(
        ge=0,
        description="Number of consecutive exercises where user struggled"
    )

    # Context
    current_difficulty: Optional[ExerciseDifficulty] = Field(
        None,
        description="Current difficulty level (from most recent exercise)"
    )
    days_since_last_exercise: Optional[int] = Field(
        None,
        ge=0,
        description="Days since user's last exercise completion"
    )


# ===================================================================
# DIFFICULTY ADJUSTMENT SCHEMAS
# ===================================================================

class DifficultyAdjustmentResponse(BaseModel):
    """
    Response schema for difficulty adjustment analysis.
    Indicates whether difficulty should change and why.
    """
    user_id: int
    should_adjust: bool = Field(
        description="Whether difficulty should be adjusted"
    )
    current_difficulty: Optional[ExerciseDifficulty] = Field(
        None,
        description="User's current difficulty level"
    )
    recommended_difficulty: Optional[ExerciseDifficulty] = Field(
        None,
        description="Recommended new difficulty level (if should_adjust is True)"
    )
    reason: Optional[str] = Field(
        None,
        description="Reason for adjustment: 'increase', 'decrease', or 'maintain'"
    )
    message: str = Field(
        description="Human-readable explanation of the decision"
    )

    # Supporting metrics
    consecutive_successes: int = Field(ge=0)
    consecutive_struggles: int = Field(ge=0)
    performance_metrics: Optional[PerformanceMetrics] = Field(
        None,
        description="Full performance metrics used in decision"
    )


class DifficultyChangeNotification(BaseModel):
    """
    Notification data when difficulty level changes.
    Used to inform the user about the change.
    """
    user_id: int
    previous_difficulty: ExerciseDifficulty
    new_difficulty: ExerciseDifficulty
    change_type: str = Field(
        description="Type of change: 'increase' or 'decrease'"
    )
    message: str = Field(
        description="Congratulatory or encouraging message to user"
    )
    reason: str = Field(
        description="Why the difficulty changed"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the change occurred"
    )


# ===================================================================
# API REQUEST SCHEMAS
# ===================================================================

class DifficultyAdjustmentRequest(BaseModel):
    """
    Request schema for manual difficulty adjustment or override.
    Allows users to manually set their difficulty level.
    """
    difficulty: ExerciseDifficulty = Field(
        description="Desired difficulty level"
    )
    reason: Optional[str] = Field(
        None,
        max_length=500,
        description="Optional reason for manual adjustment"
    )


class PerformanceAnalysisRequest(BaseModel):
    """
    Request schema for analyzing user performance.
    """
    user_id: Optional[int] = Field(
        None,
        description="User ID (optional, defaults to authenticated user)"
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Number of recent exercises to analyze"
    )
    include_metrics: bool = Field(
        default=True,
        description="Whether to include detailed performance metrics"
    )


# ===================================================================
# INTERNAL SERVICE SCHEMAS
# ===================================================================

class DifficultyBounds(BaseModel):
    """
    Difficulty bounds based on user skill level.
    Ensures difficulty stays appropriate to user's stated skill level.
    """
    min_difficulty: ExerciseDifficulty = Field(
        description="Minimum difficulty for this user's skill level"
    )
    max_difficulty: ExerciseDifficulty = Field(
        description="Maximum difficulty for this user's skill level"
    )
    recommended_start: ExerciseDifficulty = Field(
        description="Recommended starting difficulty for this skill level"
    )


class PerformanceThresholds(BaseModel):
    """
    Thresholds for determining success vs. struggle.
    Configurable parameters for the adaptation algorithm.
    """
    success_grade_threshold: float = Field(
        default=75.0,
        ge=0.0,
        le=100.0,
        description="Minimum grade to count as success"
    )
    success_max_hints: int = Field(
        default=2,
        ge=0,
        description="Maximum hints allowed for success"
    )
    struggle_grade_threshold: float = Field(
        default=60.0,
        ge=0.0,
        le=100.0,
        description="Grade below which counts as struggle"
    )
    struggle_min_hints: int = Field(
        default=4,
        ge=0,
        description="Minimum hints that indicates struggle"
    )
    expected_time_multiplier: float = Field(
        default=1.5,
        ge=1.0,
        description="Multiplier of expected time that indicates struggle"
    )
    consecutive_success_threshold: int = Field(
        default=3,
        ge=1,
        description="Consecutive successes needed to increase difficulty"
    )
    consecutive_struggle_threshold: int = Field(
        default=2,
        ge=1,
        description="Consecutive struggles needed to decrease difficulty"
    )
    max_days_for_recency: int = Field(
        default=14,
        ge=1,
        description="Maximum days for exercises to be considered 'recent'"
    )

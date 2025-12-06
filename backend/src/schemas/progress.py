"""
Pydantic schemas for progress tracking and achievement validation.

These schemas define the shape of data for:
- Progress metrics and statistics
- Achievement tracking
- Streak calculation
- Progress history
- Badge management
- Export functionality
- Skill level tracking
"""
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator


# ===================================================================
# RESPONSE SCHEMAS
# ===================================================================

class ProgressMetricsResponse(BaseModel):
    """Response schema for user progress metrics."""
    exercises_completed: int = Field(description="Total exercises completed")
    current_streak: int = Field(description="Current consecutive day streak")
    longest_streak: int = Field(description="Longest consecutive day streak ever")
    total_time_spent_seconds: int = Field(description="Total time spent on exercises")
    average_grade: Optional[float] = Field(None, description="Average grade across all exercises")
    achievements: List[Dict[str, Any]] = Field(default_factory=list, description="Unlocked achievements")
    skill_levels: Dict[str, Any] = Field(default_factory=dict, description="Skill levels by topic")

    class Config:
        from_attributes = True
        orm_mode = True


class AchievementResponse(BaseModel):
    """Response schema for a single achievement."""
    id: int
    name: str
    slug: str
    title: str
    description: str
    category: str
    requirement_value: Optional[int]
    requirement_description: str
    icon_url: Optional[str]
    badge_color: Optional[str]
    points: int
    unlocked: bool = Field(description="Whether user has unlocked this achievement")
    unlocked_at: Optional[datetime] = Field(None, description="When achievement was unlocked")
    progress: Optional[int] = Field(None, description="Current progress toward achievement")
    target: Optional[int] = Field(None, description="Target value for achievement")
    progress_percentage: Optional[float] = Field(None, description="Progress as percentage")

    class Config:
        from_attributes = True
        orm_mode = True


class AchievementsListResponse(BaseModel):
    """Response schema for list of achievements."""
    achievements: List[AchievementResponse]
    total_points: int = Field(description="Total points earned from achievements")
    unlocked_count: int = Field(description="Number of achievements unlocked")
    total_count: int = Field(description="Total number of achievements available")


class StreakUpdateResponse(BaseModel):
    """Response schema for streak update."""
    current_streak: int
    longest_streak: int
    streak_maintained: bool = Field(description="Whether streak was maintained")
    streak_broken: bool = Field(default=False, description="Whether streak was broken")
    previous_streak: Optional[int] = Field(None, description="Previous streak before break")
    new_record: bool = Field(default=False, description="Whether a new longest streak was set")
    achievements_unlocked: List[str] = Field(default_factory=list, description="New achievements from streak")


class PerformanceStatisticsResponse(BaseModel):
    """Response schema for performance statistics."""
    average_grade: float
    average_time_per_exercise: float = Field(description="Average time in seconds")
    total_hints_requested: int
    exercises_by_difficulty: Dict[str, int] = Field(description="Count by difficulty level")
    exercises_by_type: Dict[str, int] = Field(description="Count by exercise type")
    recent_performance_trend: List[Dict[str, Any]] = Field(description="Recent performance data points")
    period: Optional[str] = Field(None, description="Time period for statistics (daily/weekly/monthly)")

    class Config:
        from_attributes = True


class ProgressHistoryEntry(BaseModel):
    """Single entry in progress history."""
    date: datetime
    exercises_completed: int
    time_spent_seconds: int
    average_grade: Optional[float]
    streak: int
    achievements_unlocked: int = Field(default=0)


class ProgressHistoryResponse(BaseModel):
    """Response schema for progress history."""
    history: List[ProgressHistoryEntry]
    start_date: date
    end_date: date
    total_days: int


class BadgeResponse(BaseModel):
    """Response schema for a badge."""
    id: int
    type: str = Field(description="Badge type/key (e.g., 'streak_7')")
    name: str
    description: str
    icon_url: Optional[str]
    icon: Optional[str] = Field(None, description="Icon identifier if using icon set")
    earned: bool
    earned_at: Optional[datetime] = Field(None)
    category: str
    points: int
    rarity: Optional[str] = Field(None, description="common, rare, epic, legendary")


class BadgesListResponse(BaseModel):
    """Response schema for badges list."""
    badges: List[BadgeResponse]
    total_earned: int
    total_available: int
    points_earned: int


class SkillLevelResponse(BaseModel):
    """Response schema for skill level in a topic."""
    topic: str
    level: str = Field(description="beginner, intermediate, advanced, expert")
    exercises_completed: int
    average_grade: Optional[float]
    total_time_spent_seconds: int
    level_updated_at: Optional[datetime]
    previous_level: Optional[str]


class SkillLevelsResponse(BaseModel):
    """Response schema for all skill levels."""
    skill_levels: List[SkillLevelResponse]


class SkillLevelCalculationResponse(BaseModel):
    """Response schema for skill level calculation."""
    topic: str
    current_level: str
    previous_level: Optional[str]
    level_changed: bool
    exercises_completed: int
    average_grade: Optional[float]
    next_level: Optional[str]
    progress_to_next: Optional[float] = Field(None, description="Progress percentage to next level")


class ProgressExportResponse(BaseModel):
    """Response schema for progress export (JSON format)."""
    user_id: int
    export_date: datetime
    progress_metrics: ProgressMetricsResponse
    achievements: List[AchievementResponse]
    exercise_history: List[Dict[str, Any]]
    statistics: PerformanceStatisticsResponse


# ===================================================================
# REQUEST SCHEMAS
# ===================================================================

class StreakUpdateRequest(BaseModel):
    """Request schema for updating streak."""
    completed_today: bool = Field(description="Whether user completed exercise today")
    user_timezone: Optional[str] = Field(None, description="User timezone for accurate streak calculation")


class ProgressHistoryRequest(BaseModel):
    """Request schema for progress history query."""
    days: Optional[int] = Field(30, ge=1, le=365, description="Number of days of history")
    start_date: Optional[date] = Field(None, description="Start date for custom range")
    end_date: Optional[date] = Field(None, description="End date for custom range")


class StatisticsRequest(BaseModel):
    """Request schema for statistics query."""
    period: Optional[str] = Field(None, description="Time period: daily, weekly, monthly, all")

    @validator('period')
    def validate_period(cls, value):
        """Validate period is a known value."""
        if value and value not in ['daily', 'weekly', 'monthly', 'all']:
            raise ValueError('Period must be daily, weekly, monthly, or all')
        return value


class ExportRequest(BaseModel):
    """Request schema for progress export."""
    format: str = Field('json', description="Export format: json or csv")

    @validator('format')
    def validate_format(cls, value):
        """Validate export format."""
        if value not in ['json', 'csv']:
            raise ValueError('Format must be json or csv')
        return value


class SkillLevelCalculationRequest(BaseModel):
    """Request schema for skill level calculation."""
    topic: str = Field(description="Topic to calculate skill level for")


# ===================================================================
# INTERNAL SERVICE SCHEMAS
# ===================================================================

class StreakCalculation(BaseModel):
    """Internal schema for streak calculation logic."""
    user_id: int
    last_exercise_date: Optional[datetime]
    current_streak: int
    longest_streak: int
    today_completed: bool


class AchievementProgress(BaseModel):
    """Internal schema for tracking achievement progress."""
    achievement_id: int
    user_id: int
    current_value: int
    target_value: int
    progress_percentage: float
    unlocked: bool


class DailySnapshotData(BaseModel):
    """Internal schema for creating daily progress snapshots."""
    user_id: int
    snapshot_date: datetime
    exercises_completed_total: int
    exercises_completed_today: int
    current_streak: int
    longest_streak: int
    total_time_spent_seconds: int
    time_spent_today_seconds: int
    average_grade: Optional[float]
    average_grade_today: Optional[float]
    total_hints_requested: int
    hints_requested_today: int
    achievements_unlocked_total: int
    achievements_unlocked_today: int

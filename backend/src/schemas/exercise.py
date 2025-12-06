"""
Pydantic schemas for exercise validation and serialization.

These schemas define the shape of data for:
- Exercise creation and generation
- Exercise submission
- Hint requests
- Exercise responses
- User exercise progress
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator
from src.models.exercise import ExerciseType, ExerciseDifficulty, ExerciseStatus


# ===================================================================
# REQUEST SCHEMAS
# ===================================================================

class ExerciseGenerateRequest(BaseModel):
    """Request schema for generating a new exercise."""
    topic: Optional[str] = Field(None, description="Specific topic for the exercise")
    difficulty: Optional[str] = Field(None, description="Desired difficulty (overrides user's level)")
    exercise_type: Optional[ExerciseType] = Field(None, description="Type of exercise")

    @validator('difficulty')
    def validate_difficulty(cls, value):
        """Validate difficulty is a known value."""
        if value and value not in ['easy', 'medium', 'hard', 'beginner', 'intermediate', 'advanced']:
            raise ValueError('Difficulty must be easy, medium, hard, beginner, intermediate, or advanced')
        return value


class ExerciseSubmissionRequest(BaseModel):
    """Request schema for submitting an exercise solution."""
    solution: str = Field(..., min_length=1, description="User's code solution")
    time_spent_seconds: Optional[int] = Field(None, ge=0, description="Time spent on exercise in seconds")

    @validator('solution')
    def validate_solution_not_empty(cls, value):
        """Ensure solution is not just whitespace."""
        if not value or not value.strip():
            raise ValueError('Solution cannot be empty or only whitespace')
        return value.strip()


class HintRequest(BaseModel):
    """Request schema for requesting a hint."""
    context: Optional[str] = Field(None, description="Additional context about where user is stuck")
    current_code: Optional[str] = Field(None, description="User's current code attempt")


class ExerciseListRequest(BaseModel):
    """Request schema for listing exercises with filters."""
    status: Optional[ExerciseStatus] = Field(None, description="Filter by status")
    limit: int = Field(20, ge=1, le=100, description="Number of exercises to return")
    offset: int = Field(0, ge=0, description="Pagination offset")
    programming_language: Optional[str] = Field(None, description="Filter by language")
    difficulty: Optional[ExerciseDifficulty] = Field(None, description="Filter by difficulty")


# ===================================================================
# RESPONSE SCHEMAS
# ===================================================================

class ExerciseResponse(BaseModel):
    """Response schema for a single exercise."""
    id: int
    title: str
    description: str
    instructions: str
    starter_code: Optional[str]
    exercise_type: ExerciseType
    difficulty: ExerciseDifficulty
    programming_language: str
    topics: Optional[str]
    test_cases: Optional[str]
    generated_by_ai: bool
    created_at: datetime

    class Config:
        from_attributes = True  # Pydantic v2
        orm_mode = True  # Pydantic v1 compatibility


class UserExerciseResponse(BaseModel):
    """Response schema for user's progress on an exercise."""
    id: int
    exercise_id: int
    user_id: int
    status: ExerciseStatus
    hints_requested: int
    grade: Optional[float]
    ai_feedback: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    time_spent_seconds: Optional[int]
    test_cases_passed: Optional[int]
    test_cases_total: Optional[int]

    class Config:
        from_attributes = True
        orm_mode = True


class DailyExerciseResponse(BaseModel):
    """Response schema for daily exercise endpoint."""
    exercise: ExerciseResponse
    user_exercise_id: int
    status: ExerciseStatus
    hints_used: int
    started_at: Optional[datetime]
    is_new: bool = Field(description="Whether this is a newly generated exercise")


class ExerciseSubmissionResponse(BaseModel):
    """Response schema for exercise submission evaluation."""
    grade: float = Field(ge=0.0, le=100.0, description="Grade out of 100")
    feedback: str
    strengths: List[str]
    improvements: List[str]
    status: ExerciseStatus
    hints_used: int
    submission_count: int = Field(description="Number of times user has submitted this exercise")


class HintResponse(BaseModel):
    """Response schema for hint request."""
    hint: str
    hints_used: int
    hints_remaining: Optional[int] = Field(None, description="Remaining hints (if limited)")
    difficulty_level: int = Field(ge=1, le=3, description="Difficulty level of hint (1=gentle nudge, 3=more explicit)")


class ExerciseListResponse(BaseModel):
    """Response schema for exercise list endpoint."""
    exercises: List[Dict[str, Any]]  # List of exercises with user progress
    total: int
    limit: int
    offset: int
    has_more: bool


class ExerciseCompletionResponse(BaseModel):
    """Response schema for marking exercise complete."""
    exercise_id: int
    user_exercise_id: int
    status: ExerciseStatus
    completed_at: datetime
    streak_count: int = Field(description="Current streak of consecutive days")
    achievements_unlocked: List[str] = Field(default_factory=list, description="Newly unlocked achievements")


# ===================================================================
# INTERNAL SERVICE SCHEMAS
# ===================================================================

class LLMExerciseGenerationContext(BaseModel):
    """Context for LLM exercise generation."""
    programming_language: str
    skill_level: str
    learning_goals: Optional[str]
    preferred_topics: Optional[str]
    difficulty_override: Optional[str]
    topic_override: Optional[str]
    exercise_type: Optional[ExerciseType]
    previous_topics: List[str] = Field(default_factory=list, description="Recently covered topics to avoid")


class LLMHintContext(BaseModel):
    """Context for LLM hint generation."""
    exercise_title: str
    exercise_description: str
    exercise_instructions: str
    user_code: Optional[str]
    user_context: Optional[str]
    hints_already_given: int
    difficulty: ExerciseDifficulty


class LLMEvaluationContext(BaseModel):
    """Context for LLM code evaluation."""
    exercise_title: str
    exercise_description: str
    exercise_instructions: str
    solution_code: str
    expected_solution: Optional[str]
    test_cases: Optional[str]
    programming_language: str
    skill_level: str

"""
Pydantic schemas for user profile and onboarding.
"""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from src.models.user import SkillLevel, UserRole


class OnboardingRequest(BaseModel):
    """Schema for onboarding interview completion."""
    programming_language: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Primary programming language (e.g., python, javascript, java)"
    )
    skill_level: SkillLevel = Field(
        ...,
        description="Current skill level"
    )
    career_goals: str = Field(
        ...,
        min_length=10,
        max_length=1000,
        description="User's career goals and aspirations"
    )
    learning_style: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Preferred learning style (e.g., hands-on, visual, reading)"
    )
    time_commitment: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Daily time commitment (e.g., 1-2 hours/day, 30 minutes/day)"
    )

    @field_validator('programming_language')
    @classmethod
    def validate_language(cls, value: str) -> str:
        """Validate and normalize programming language."""
        normalized = value.strip().lower()

        # List of supported languages
        supported_languages = [
            'python', 'javascript', 'typescript', 'java', 'c++', 'cpp',
            'c#', 'csharp', 'go', 'rust', 'ruby', 'php', 'swift',
            'kotlin', 'scala', 'r', 'dart', 'c'
        ]

        if normalized not in supported_languages:
            raise ValueError(
                f"Unsupported language. Supported: {', '.join(supported_languages)}"
            )

        return normalized

    @field_validator('career_goals')
    @classmethod
    def validate_career_goals(cls, value: str) -> str:
        """Validate career goals field."""
        stripped = value.strip()
        if len(stripped) < 10:
            raise ValueError("Career goals must be at least 10 characters")
        return stripped


class OnboardingResponse(BaseModel):
    """Schema for onboarding completion response."""
    user_id: int
    email: str
    name: str
    programming_language: str
    skill_level: SkillLevel
    career_goals: str
    learning_style: str
    time_commitment: str
    onboarding_completed: bool
    message: str


class ProfileUpdateRequest(BaseModel):
    """Schema for user profile update."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    bio: Optional[str] = Field(None, max_length=2000)
    programming_language: Optional[str] = Field(None, min_length=1, max_length=50)
    skill_level: Optional[SkillLevel] = None
    career_goals: Optional[str] = Field(None, min_length=10, max_length=1000)
    learning_style: Optional[str] = Field(None, min_length=3, max_length=100)
    time_commitment: Optional[str] = Field(None, min_length=3, max_length=100)

    @field_validator('programming_language')
    @classmethod
    def validate_language(cls, value: Optional[str]) -> Optional[str]:
        """Validate and normalize programming language."""
        if value is None:
            return None

        normalized = value.strip().lower()

        supported_languages = [
            'python', 'javascript', 'typescript', 'java', 'c++', 'cpp',
            'c#', 'csharp', 'go', 'rust', 'ruby', 'php', 'swift',
            'kotlin', 'scala', 'r', 'dart', 'c'
        ]

        if normalized not in supported_languages:
            raise ValueError(
                f"Unsupported language. Supported: {', '.join(supported_languages)}"
            )

        return normalized


class UserProfileResponse(BaseModel):
    """Schema for complete user profile."""
    id: int
    email: str
    name: str
    avatar_url: Optional[str]
    bio: Optional[str]

    # Preferences
    programming_language: Optional[str]
    skill_level: Optional[SkillLevel]
    career_goals: Optional[str]
    learning_style: Optional[str]
    time_commitment: Optional[str]

    # Role and status
    role: UserRole
    is_active: bool
    is_mentor: bool

    # Progress
    current_streak: int
    longest_streak: int
    exercises_completed: int
    last_exercise_date: Optional[datetime]

    # Onboarding
    onboarding_completed: bool

    # Timestamps
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime]

    model_config = {
        "from_attributes": True
    }


class UserProgressResponse(BaseModel):
    """Schema for user progress statistics."""
    user_id: int
    current_streak: int
    longest_streak: int
    exercises_completed: int
    last_exercise_date: Optional[datetime]
    skill_level: Optional[SkillLevel]
    onboarding_completed: bool
    member_since: datetime


class OnboardingQuestionsResponse(BaseModel):
    """Schema for onboarding interview questions."""
    questions: list[dict]
    total_questions: int
    estimated_time: str

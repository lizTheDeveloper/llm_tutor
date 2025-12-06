"""
Exercise Service - Business logic for exercise generation and management.

This service handles:
- Daily exercise generation (personalized to user)
- Exercise retrieval and listing
- Exercise submission and evaluation
- Hint generation
- Exercise completion tracking
- Integration with LLM for generation, hints, and evaluation
"""
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User
from src.models.exercise import Exercise, UserExercise, ExerciseType, ExerciseDifficulty, ExerciseStatus
from src.models.user_memory import UserMemory
from src.schemas.exercise import (
    LLMExerciseGenerationContext,
    LLMHintContext,
    LLMEvaluationContext,
)
from src.services.llm.llm_service import LLMService
from src.logging_config import get_logger

logger = get_logger(__name__)


class ExerciseService:
    """Service for managing exercises and user exercise progress."""

    def __init__(self, session: AsyncSession):
        """
        Initialize exercise service.

        Args:
            session: Database session
        """
        self.session = session
        self.llm_service = LLMService()

    # ===================================================================
    # DAILY EXERCISE GENERATION
    # ===================================================================

    async def get_or_generate_daily_exercise(self, user_id: int) -> Tuple[Exercise, UserExercise, bool]:
        """
        Get today's exercise for user, or generate a new one if needed.

        Args:
            user_id: User ID

        Returns:
            Tuple of (Exercise, UserExercise, is_new)
        """
        logger.info("Getting daily exercise for user", extra={"user_id": user_id})

        # Check if user has an uncompleted exercise from today
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        stmt = (
            select(UserExercise)
            .where(
                and_(
                    UserExercise.user_id == user_id,
                    UserExercise.created_at >= today_start,
                    UserExercise.status.in_([ExerciseStatus.PENDING, ExerciseStatus.IN_PROGRESS])
                )
            )
            .order_by(desc(UserExercise.created_at))
        )

        result = await self.session.execute(stmt)
        user_exercise = result.scalar_one_or_none()

        if user_exercise:
            # Fetch the associated exercise
            exercise = await self.get_exercise_by_id(user_exercise.exercise_id)
            logger.info("Found existing daily exercise", extra={
                "user_id": user_id,
                "exercise_id": exercise.id
            })
            return exercise, user_exercise, False

        # Generate new exercise
        logger.info("Generating new daily exercise", extra={"user_id": user_id})
        exercise, user_exercise = await self.generate_personalized_exercise(user_id)

        return exercise, user_exercise, True

    async def generate_personalized_exercise(
        self,
        user_id: int,
        topic: Optional[str] = None,
        difficulty: Optional[str] = None,
        exercise_type: Optional[ExerciseType] = None
    ) -> Tuple[Exercise, UserExercise]:
        """
        Generate a personalized exercise using LLM.

        Args:
            user_id: User ID
            topic: Optional topic override
            difficulty: Optional difficulty override
            exercise_type: Optional exercise type

        Returns:
            Tuple of (Exercise, UserExercise)
        """
        # Get user profile
        user = await self._get_user(user_id)

        # Get user's recent topics to avoid repetition
        recent_topics = await self._get_recent_topics(user_id, limit=5)

        # Build LLM context
        context = LLMExerciseGenerationContext(
            programming_language=user.primary_language or "python",
            skill_level=user.skill_level or "intermediate",
            learning_goals=user.learning_goals,
            preferred_topics=user.preferred_topics,
            difficulty_override=difficulty,
            topic_override=topic,
            exercise_type=exercise_type,
            previous_topics=recent_topics
        )

        logger.info("Generating exercise with LLM", extra={
            "user_id": user_id,
            "language": context.programming_language,
            "skill_level": context.skill_level
        })

        # Generate exercise using LLM
        exercise_data = await self.llm_service.generate_exercise(context)

        # Create Exercise record
        exercise = Exercise(
            title=exercise_data["title"],
            description=exercise_data["description"],
            instructions=exercise_data["instructions"],
            starter_code=exercise_data.get("starter_code"),
            solution=exercise_data.get("solution"),
            exercise_type=ExerciseType(exercise_data.get("type", "algorithm")),
            difficulty=self._map_difficulty(exercise_data.get("difficulty", "medium")),
            programming_language=context.programming_language,
            topics=",".join(exercise_data.get("topics", [])),
            test_cases=json.dumps(exercise_data.get("test_cases", [])),
            generated_by_ai=True,
            generation_prompt=str(context.dict())
        )

        self.session.add(exercise)
        await self.session.flush()  # Get exercise ID

        # Create UserExercise record
        user_exercise = UserExercise(
            user_id=user_id,
            exercise_id=exercise.id,
            status=ExerciseStatus.PENDING,
            started_at=datetime.utcnow()
        )

        self.session.add(user_exercise)
        await self.session.flush()

        logger.info("Exercise generated successfully", extra={
            "user_id": user_id,
            "exercise_id": exercise.id,
            "title": exercise.title
        })

        return exercise, user_exercise

    # ===================================================================
    # EXERCISE RETRIEVAL
    # ===================================================================

    async def get_exercise_by_id(self, exercise_id: int) -> Exercise:
        """
        Get exercise by ID.

        Args:
            exercise_id: Exercise ID

        Returns:
            Exercise

        Raises:
            ValueError: If exercise not found
        """
        stmt = select(Exercise).where(Exercise.id == exercise_id)
        result = await self.session.execute(stmt)
        exercise = result.scalar_one_or_none()

        if not exercise:
            raise ValueError(f"Exercise {exercise_id} not found")

        return exercise

    async def get_user_exercise(self, user_id: int, exercise_id: int) -> Optional[UserExercise]:
        """
        Get user's progress on an exercise.

        Args:
            user_id: User ID
            exercise_id: Exercise ID

        Returns:
            UserExercise or None
        """
        stmt = select(UserExercise).where(
            and_(
                UserExercise.user_id == user_id,
                UserExercise.exercise_id == exercise_id
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_user_exercises(
        self,
        user_id: int,
        status: Optional[ExerciseStatus] = None,
        limit: int = 20,
        offset: int = 0
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        List user's exercises with optional filtering.

        Args:
            user_id: User ID
            status: Optional status filter
            limit: Number of results
            offset: Pagination offset

        Returns:
            Tuple of (exercises list, total count)
        """
        # Build base query
        base_stmt = (
            select(UserExercise, Exercise)
            .join(Exercise, UserExercise.exercise_id == Exercise.id)
            .where(UserExercise.user_id == user_id)
        )

        if status:
            base_stmt = base_stmt.where(UserExercise.status == status)

        # Get total count
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar()

        # Get paginated results
        stmt = base_stmt.order_by(desc(UserExercise.created_at)).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        rows = result.all()

        # Format results
        exercises = []
        for user_ex, exercise in rows:
            exercises.append({
                "exercise_id": exercise.id,
                "user_exercise_id": user_ex.id,
                "title": exercise.title,
                "description": exercise.description,
                "difficulty": exercise.difficulty.value,
                "programming_language": exercise.programming_language,
                "status": user_ex.status.value,
                "grade": user_ex.grade,
                "hints_requested": user_ex.hints_requested,
                "started_at": user_ex.started_at.isoformat() if user_ex.started_at else None,
                "completed_at": user_ex.completed_at.isoformat() if user_ex.completed_at else None,
                "time_spent_seconds": user_ex.time_spent_seconds
            })

        return exercises, total

    # ===================================================================
    # EXERCISE SUBMISSION
    # ===================================================================

    async def submit_exercise(
        self,
        user_id: int,
        exercise_id: int,
        solution: str,
        time_spent: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Submit and evaluate an exercise solution.

        Args:
            user_id: User ID
            exercise_id: Exercise ID
            solution: User's code solution
            time_spent: Time spent in seconds

        Returns:
            Evaluation results
        """
        logger.info("Processing exercise submission", extra={
            "user_id": user_id,
            "exercise_id": exercise_id
        })

        # Get exercise and user exercise
        exercise = await self.get_exercise_by_id(exercise_id)
        user_exercise = await self.get_user_exercise(user_id, exercise_id)

        if not user_exercise:
            # Create new UserExercise if doesn't exist
            user_exercise = UserExercise(
                user_id=user_id,
                exercise_id=exercise_id,
                status=ExerciseStatus.IN_PROGRESS,
                started_at=datetime.utcnow()
            )
            self.session.add(user_exercise)

        # Get user for context
        user = await self._get_user(user_id)

        # Build evaluation context
        context = LLMEvaluationContext(
            exercise_title=exercise.title,
            exercise_description=exercise.description,
            exercise_instructions=exercise.instructions,
            solution_code=solution,
            expected_solution=exercise.solution,
            test_cases=exercise.test_cases,
            programming_language=exercise.programming_language,
            skill_level=user.skill_level or "intermediate"
        )

        # Evaluate with LLM
        evaluation = await self.llm_service.evaluate_submission(context)

        # Update user exercise
        user_exercise.user_solution = solution
        user_exercise.grade = evaluation["grade"]
        user_exercise.ai_feedback = evaluation["feedback"]
        user_exercise.status = ExerciseStatus.IN_PROGRESS  # Still in progress unless marked complete

        if time_spent:
            user_exercise.time_spent_seconds = time_spent

        await self.session.flush()

        logger.info("Exercise submission evaluated", extra={
            "user_id": user_id,
            "exercise_id": exercise_id,
            "grade": evaluation["grade"]
        })

        return {
            "grade": evaluation["grade"],
            "feedback": evaluation["feedback"],
            "strengths": evaluation.get("strengths", []),
            "improvements": evaluation.get("improvements", []),
            "status": user_exercise.status.value,
            "hints_used": user_exercise.hints_requested,
            "submission_count": 1  # TODO: Track submission count
        }

    # ===================================================================
    # HINTS
    # ===================================================================

    async def request_hint(
        self,
        user_id: int,
        exercise_id: int,
        context: Optional[str] = None,
        current_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a hint for an exercise.

        Args:
            user_id: User ID
            exercise_id: Exercise ID
            context: Additional context from user
            current_code: User's current code

        Returns:
            Hint response
        """
        logger.info("Generating hint", extra={
            "user_id": user_id,
            "exercise_id": exercise_id
        })

        # Get exercise and user exercise
        exercise = await self.get_exercise_by_id(exercise_id)
        user_exercise = await self.get_user_exercise(user_id, exercise_id)

        if not user_exercise:
            # Create UserExercise if it doesn't exist
            user_exercise = UserExercise(
                user_id=user_id,
                exercise_id=exercise_id,
                status=ExerciseStatus.IN_PROGRESS,
                started_at=datetime.utcnow()
            )
            self.session.add(user_exercise)

        # Build hint context
        hint_context = LLMHintContext(
            exercise_title=exercise.title,
            exercise_description=exercise.description,
            exercise_instructions=exercise.instructions,
            user_code=current_code,
            user_context=context,
            hints_already_given=user_exercise.hints_requested,
            difficulty=exercise.difficulty
        )

        # Generate hint with LLM
        hint_data = await self.llm_service.generate_hint(hint_context)

        # Increment hint counter
        user_exercise.hints_requested += 1
        await self.session.flush()

        logger.info("Hint generated", extra={
            "user_id": user_id,
            "exercise_id": exercise_id,
            "hints_used": user_exercise.hints_requested
        })

        return {
            "hint": hint_data["hint"],
            "hints_used": user_exercise.hints_requested,
            "difficulty_level": min(user_exercise.hints_requested, 3)
        }

    # ===================================================================
    # EXERCISE COMPLETION
    # ===================================================================

    async def mark_complete(self, user_id: int, exercise_id: int) -> Dict[str, Any]:
        """
        Mark an exercise as complete.

        Args:
            user_id: User ID
            exercise_id: Exercise ID

        Returns:
            Completion response with streak info
        """
        logger.info("Marking exercise complete", extra={
            "user_id": user_id,
            "exercise_id": exercise_id
        })

        user_exercise = await self.get_user_exercise(user_id, exercise_id)

        if not user_exercise:
            raise ValueError("User exercise not found")

        # Mark as complete
        user_exercise.status = ExerciseStatus.COMPLETED
        user_exercise.completed_at = datetime.utcnow()

        await self.session.flush()

        # Calculate streak (TODO: Move to dedicated service)
        streak_count = await self._calculate_streak(user_id)

        logger.info("Exercise marked complete", extra={
            "user_id": user_id,
            "exercise_id": exercise_id,
            "streak": streak_count
        })

        return {
            "exercise_id": exercise_id,
            "user_exercise_id": user_exercise.id,
            "status": ExerciseStatus.COMPLETED.value,
            "completed_at": user_exercise.completed_at,
            "streak_count": streak_count,
            "achievements_unlocked": []  # TODO: Implement achievement system
        }

    # ===================================================================
    # HELPER METHODS
    # ===================================================================

    async def _get_user(self, user_id: int) -> User:
        """Get user by ID."""
        stmt = select(User).where(User.id == user_id)
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            raise ValueError(f"User {user_id} not found")

        return user

    async def _get_recent_topics(self, user_id: int, limit: int = 5) -> List[str]:
        """Get user's recently covered topics to avoid repetition."""
        stmt = (
            select(Exercise.topics)
            .join(UserExercise, Exercise.id == UserExercise.exercise_id)
            .where(UserExercise.user_id == user_id)
            .order_by(desc(UserExercise.created_at))
            .limit(limit)
        )

        result = await self.session.execute(stmt)
        topic_strings = result.scalars().all()

        # Parse comma-separated topics
        topics = []
        for topic_str in topic_strings:
            if topic_str:
                topics.extend(topic_str.split(","))

        return list(set(topics))  # Return unique topics

    def _map_difficulty(self, difficulty: str) -> ExerciseDifficulty:
        """Map difficulty string to enum."""
        difficulty_map = {
            "easy": ExerciseDifficulty.EASY,
            "beginner": ExerciseDifficulty.EASY,
            "medium": ExerciseDifficulty.MEDIUM,
            "intermediate": ExerciseDifficulty.MEDIUM,
            "hard": ExerciseDifficulty.HARD,
            "advanced": ExerciseDifficulty.HARD,
        }
        return difficulty_map.get(difficulty.lower(), ExerciseDifficulty.MEDIUM)

    async def _calculate_streak(self, user_id: int) -> int:
        """
        Calculate user's current exercise completion streak.

        Returns consecutive days with completed exercises.
        """
        # Get all completed exercises ordered by completion date
        stmt = (
            select(func.date(UserExercise.completed_at))
            .where(
                and_(
                    UserExercise.user_id == user_id,
                    UserExercise.status == ExerciseStatus.COMPLETED,
                    UserExercise.completed_at.isnot(None)
                )
            )
            .distinct()
            .order_by(desc(func.date(UserExercise.completed_at)))
        )

        result = await self.session.execute(stmt)
        completion_dates = [row[0] for row in result.all()]

        if not completion_dates:
            return 0

        # Calculate streak
        streak = 1
        today = datetime.utcnow().date()
        current_date = completion_dates[0]

        # Check if most recent completion was today or yesterday
        if current_date not in [today, today - timedelta(days=1)]:
            return 0

        # Count consecutive days
        for i in range(1, len(completion_dates)):
            expected_date = current_date - timedelta(days=i)
            if completion_dates[i] == expected_date:
                streak += 1
            else:
                break

        return streak

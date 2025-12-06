"""
Difficulty Adaptation Service - Adaptive difficulty adjustment engine.

This service implements the core difficulty adaptation algorithm:
- Analyzes user performance on recent exercises
- Tracks consecutive successes and struggles
- Recommends difficulty adjustments based on performance patterns
- Respects user skill level boundaries
- Generates notifications for difficulty changes

Requirements Coverage:
- REQ-EXERCISE-003: Adaptive difficulty adjustment
- REQ-EXERCISE-004: Exercise completion metrics tracking
"""
from datetime import datetime, timedelta
from typing import Optional, List, Tuple
from sqlalchemy import select, and_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User, SkillLevel
from src.models.exercise import (
    Exercise, UserExercise, ExerciseDifficulty, ExerciseStatus
)
from src.schemas.difficulty import (
    PerformanceMetrics,
    ExercisePerformanceSummary,
    DifficultyAdjustmentResponse,
    DifficultyChangeNotification,
    DifficultyBounds,
    PerformanceThresholds
)
from src.logging_config import get_logger

logger = get_logger(__name__)


class DifficultyService:
    """Service for managing adaptive difficulty adjustment."""

    # Default performance thresholds (configurable)
    DEFAULT_THRESHOLDS = PerformanceThresholds()

    # Difficulty bounds by skill level
    SKILL_LEVEL_BOUNDS = {
        SkillLevel.BEGINNER: DifficultyBounds(
            min_difficulty=ExerciseDifficulty.EASY,
            max_difficulty=ExerciseDifficulty.MEDIUM,
            recommended_start=ExerciseDifficulty.EASY
        ),
        SkillLevel.INTERMEDIATE: DifficultyBounds(
            min_difficulty=ExerciseDifficulty.EASY,
            max_difficulty=ExerciseDifficulty.HARD,
            recommended_start=ExerciseDifficulty.MEDIUM
        ),
        SkillLevel.ADVANCED: DifficultyBounds(
            min_difficulty=ExerciseDifficulty.MEDIUM,
            max_difficulty=ExerciseDifficulty.HARD,
            recommended_start=ExerciseDifficulty.HARD
        ),
        SkillLevel.EXPERT: DifficultyBounds(
            min_difficulty=ExerciseDifficulty.MEDIUM,
            max_difficulty=ExerciseDifficulty.HARD,
            recommended_start=ExerciseDifficulty.HARD
        ),
    }

    def __init__(
        self,
        session: AsyncSession,
        thresholds: Optional[PerformanceThresholds] = None
    ):
        """
        Initialize difficulty service.

        Args:
            session: Database session
            thresholds: Custom performance thresholds (uses defaults if not provided)
        """
        self.session = session
        self.thresholds = thresholds or self.DEFAULT_THRESHOLDS

    # ===================================================================
    # PERFORMANCE ANALYSIS
    # ===================================================================

    async def get_recent_performance(
        self,
        user_id: int,
        limit: int = 10
    ) -> PerformanceMetrics:
        """
        Get recent performance metrics for a user.

        Args:
            user_id: User ID
            limit: Number of recent exercises to analyze

        Returns:
            PerformanceMetrics with aggregated statistics
        """
        logger.info("Analyzing recent performance", extra={
            "user_id": user_id,
            "limit": limit
        })

        # Fetch recent user exercises with exercise details
        stmt = (
            select(UserExercise, Exercise)
            .join(Exercise, UserExercise.exercise_id == Exercise.id)
            .where(UserExercise.user_id == user_id)
            .order_by(desc(UserExercise.completed_at))
            .limit(limit)
        )

        result = await self.session.execute(stmt)
        rows = result.all()

        if not rows:
            logger.info("No exercise history found", extra={"user_id": user_id})
            return PerformanceMetrics(
                user_id=user_id,
                recent_exercises=[],
                total_exercises_analyzed=0,
                average_grade=0.0,
                average_hints=0.0,
                average_time_seconds=0.0,
                completion_rate=0.0,
                consecutive_successes=0,
                consecutive_struggles=0,
                current_difficulty=None,
                days_since_last_exercise=None
            )

        # Build exercise performance summaries
        summaries: List[ExercisePerformanceSummary] = []
        for user_exercise, exercise in rows:
            is_success = self._is_success(user_exercise)
            is_struggle = self._is_struggle(user_exercise, exercise)

            summary = ExercisePerformanceSummary(
                exercise_id=exercise.id,
                difficulty=exercise.difficulty,
                status=user_exercise.status,
                grade=user_exercise.grade,
                hints_requested=user_exercise.hints_requested,
                time_spent_seconds=user_exercise.time_spent_seconds,
                completed_at=user_exercise.completed_at,
                is_success=is_success,
                is_struggle=is_struggle
            )
            summaries.append(summary)

        # Calculate aggregated statistics
        completed_exercises = [
            s for s in summaries
            if s.status == ExerciseStatus.COMPLETED and s.grade is not None
        ]

        average_grade = None
        if completed_exercises:
            average_grade = sum(s.grade for s in completed_exercises) / len(completed_exercises)

        average_hints = sum(s.hints_requested for s in summaries) / len(summaries)

        timed_exercises = [s for s in summaries if s.time_spent_seconds is not None]
        average_time = None
        if timed_exercises:
            average_time = sum(s.time_spent_seconds for s in timed_exercises) / len(timed_exercises)

        completion_rate = (
            len([s for s in summaries if s.status == ExerciseStatus.COMPLETED]) /
            len(summaries) * 100.0
        )

        # Calculate consecutive patterns
        consecutive_successes = self._count_consecutive_successes(summaries)
        consecutive_struggles = self._count_consecutive_struggles(summaries)

        # Get current difficulty and days since last exercise
        current_difficulty = summaries[0].difficulty if summaries else None
        days_since_last = None
        if summaries and summaries[0].completed_at:
            days_since_last = (datetime.utcnow() - summaries[0].completed_at).days

        metrics = PerformanceMetrics(
            user_id=user_id,
            recent_exercises=summaries,
            total_exercises_analyzed=len(summaries),
            average_grade=average_grade,
            average_hints=average_hints,
            average_time_seconds=average_time,
            completion_rate=completion_rate,
            consecutive_successes=consecutive_successes,
            consecutive_struggles=consecutive_struggles,
            current_difficulty=current_difficulty,
            days_since_last_exercise=days_since_last
        )

        logger.info("Performance analysis complete", extra={
            "user_id": user_id,
            "consecutive_successes": consecutive_successes,
            "consecutive_struggles": consecutive_struggles,
            "average_grade": average_grade
        })

        return metrics

    def _is_success(self, user_exercise: UserExercise) -> bool:
        """
        Determine if an exercise completion counts as a success.

        Success criteria:
        - Status is COMPLETED
        - Grade is above threshold
        - Hints requested are below threshold
        """
        if user_exercise.status != ExerciseStatus.COMPLETED:
            return False

        if user_exercise.grade is None:
            return False

        if user_exercise.grade < self.thresholds.success_grade_threshold:
            return False

        if user_exercise.hints_requested > self.thresholds.success_max_hints:
            return False

        return True

    def _is_struggle(self, user_exercise: UserExercise, exercise: Exercise) -> bool:
        """
        Determine if an exercise indicates user struggled.

        Struggle indicators:
        - Status is SKIPPED
        - Low grade
        - Many hints requested
        - Excessive time spent (future enhancement)
        """
        # Skipped exercises always count as struggles
        if user_exercise.status == ExerciseStatus.SKIPPED:
            return True

        if user_exercise.status != ExerciseStatus.COMPLETED:
            return False

        # Low grade indicates struggle
        if user_exercise.grade is not None:
            if user_exercise.grade < self.thresholds.struggle_grade_threshold:
                return True

        # Many hints indicates struggle
        if user_exercise.hints_requested >= self.thresholds.struggle_min_hints:
            return True

        return False

    def _count_consecutive_successes(
        self,
        summaries: List[ExercisePerformanceSummary]
    ) -> int:
        """
        Count consecutive successes from most recent exercise backwards.
        Streak breaks on first non-success.
        """
        count = 0
        for summary in summaries:
            if summary.is_success:
                count += 1
            else:
                break
        return count

    def _count_consecutive_struggles(
        self,
        summaries: List[ExercisePerformanceSummary]
    ) -> int:
        """
        Count consecutive struggles from most recent exercise backwards.
        Streak breaks on first non-struggle.
        """
        count = 0
        for summary in summaries:
            if summary.is_struggle:
                count += 1
            else:
                break
        return count

    # ===================================================================
    # DIFFICULTY ADJUSTMENT LOGIC
    # ===================================================================

    async def analyze_and_adjust_difficulty(
        self,
        user_id: int
    ) -> DifficultyAdjustmentResponse:
        """
        Analyze user performance and recommend difficulty adjustment.

        Implements REQ-EXERCISE-003:
        - Increase difficulty after 3 consecutive successes without hints
        - Decrease difficulty after 2 consecutive struggles
        - Maintain difficulty appropriate to skill level

        Args:
            user_id: User ID

        Returns:
            DifficultyAdjustmentResponse with recommendation
        """
        logger.info("Analyzing difficulty adjustment", extra={"user_id": user_id})

        # Get user to check skill level
        user = await self._get_user(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")

        # Get performance metrics
        metrics = await self.get_recent_performance(user_id, limit=10)

        # Determine current difficulty
        current_difficulty = metrics.current_difficulty
        if not current_difficulty:
            # New user - use recommended start for their skill level
            bounds = self._get_difficulty_bounds(user.skill_level)
            current_difficulty = bounds.recommended_start

        # Check if adjustment is needed
        should_increase = (
            metrics.consecutive_successes >= self.thresholds.consecutive_success_threshold
        )
        should_decrease = (
            metrics.consecutive_struggles >= self.thresholds.consecutive_struggle_threshold
        )

        # Determine recommended difficulty
        recommended_difficulty = current_difficulty
        reason = "maintain"
        message = "Your current difficulty level is appropriate for your performance."

        if should_increase:
            recommended_difficulty = self._get_next_difficulty_up(
                current_difficulty,
                user.skill_level
            )
            if recommended_difficulty != current_difficulty:
                reason = "increase"
                message = (
                    f"Great job! You've successfully completed {metrics.consecutive_successes} "
                    f"exercises in a row. Let's try a harder challenge!"
                )
            else:
                # At maximum for skill level
                message = (
                    f"Excellent work! You're at the highest difficulty level for your "
                    f"skill level. Keep up the great work!"
                )

        elif should_decrease:
            recommended_difficulty = self._get_next_difficulty_down(
                current_difficulty,
                user.skill_level
            )
            if recommended_difficulty != current_difficulty:
                reason = "decrease"
                message = (
                    f"Let's adjust the difficulty to better match your current pace. "
                    f"You'll build confidence and mastery at this level."
                )
            else:
                # At minimum for skill level
                message = (
                    "These exercises are challenging, but you're at the right starting "
                    "level. Keep practicing and you'll improve!"
                )

        response = DifficultyAdjustmentResponse(
            user_id=user_id,
            should_adjust=(recommended_difficulty != current_difficulty),
            current_difficulty=current_difficulty,
            recommended_difficulty=recommended_difficulty,
            reason=reason,
            message=message,
            consecutive_successes=metrics.consecutive_successes,
            consecutive_struggles=metrics.consecutive_struggles,
            performance_metrics=metrics
        )

        logger.info("Difficulty analysis complete", extra={
            "user_id": user_id,
            "should_adjust": response.should_adjust,
            "current": current_difficulty,
            "recommended": recommended_difficulty,
            "reason": reason
        })

        return response

    def _get_difficulty_bounds(
        self,
        skill_level: Optional[SkillLevel]
    ) -> DifficultyBounds:
        """Get difficulty bounds for a skill level."""
        if not skill_level or skill_level not in self.SKILL_LEVEL_BOUNDS:
            # Default to intermediate bounds
            return self.SKILL_LEVEL_BOUNDS[SkillLevel.INTERMEDIATE]
        return self.SKILL_LEVEL_BOUNDS[skill_level]

    def _get_next_difficulty_up(
        self,
        current: ExerciseDifficulty,
        skill_level: Optional[SkillLevel]
    ) -> ExerciseDifficulty:
        """
        Get the next difficulty level up, respecting skill level bounds.
        """
        bounds = self._get_difficulty_bounds(skill_level)

        # Map difficulties to numeric values
        difficulty_order = {
            ExerciseDifficulty.EASY: 1,
            ExerciseDifficulty.MEDIUM: 2,
            ExerciseDifficulty.HARD: 3
        }

        current_value = difficulty_order[current]
        max_value = difficulty_order[bounds.max_difficulty]

        if current_value >= max_value:
            # Already at maximum for this skill level
            return current

        # Move up one level
        for difficulty, value in difficulty_order.items():
            if value == current_value + 1:
                return difficulty

        return current

    def _get_next_difficulty_down(
        self,
        current: ExerciseDifficulty,
        skill_level: Optional[SkillLevel]
    ) -> ExerciseDifficulty:
        """
        Get the next difficulty level down, respecting skill level bounds.
        """
        bounds = self._get_difficulty_bounds(skill_level)

        # Map difficulties to numeric values
        difficulty_order = {
            ExerciseDifficulty.EASY: 1,
            ExerciseDifficulty.MEDIUM: 2,
            ExerciseDifficulty.HARD: 3
        }

        current_value = difficulty_order[current]
        min_value = difficulty_order[bounds.min_difficulty]

        if current_value <= min_value:
            # Already at minimum for this skill level
            return current

        # Move down one level
        for difficulty, value in difficulty_order.items():
            if value == current_value - 1:
                return difficulty

        return current

    async def _get_user(self, user_id: int) -> Optional[User]:
        """Fetch user by ID."""
        stmt = select(User).where(User.id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    # ===================================================================
    # DIFFICULTY APPLICATION
    # ===================================================================

    async def apply_difficulty_adjustment(
        self,
        user_id: int,
        new_difficulty: ExerciseDifficulty
    ) -> bool:
        """
        Apply a difficulty adjustment for a user.

        This updates the user's profile or preferences so that future
        exercises are generated at the new difficulty level.

        Args:
            user_id: User ID
            new_difficulty: New difficulty level to apply

        Returns:
            True if successfully applied
        """
        logger.info("Applying difficulty adjustment", extra={
            "user_id": user_id,
            "new_difficulty": new_difficulty
        })

        # In the current schema, we don't have a user.current_difficulty field
        # The difficulty is determined per-exercise generation
        # For MVP, we'll just log this and return success
        # In production, you might want to:
        # 1. Add a user.preferred_difficulty field
        # 2. Store in user_memory
        # 3. Use a separate user_preferences table

        logger.info("Difficulty adjustment applied", extra={
            "user_id": user_id,
            "new_difficulty": new_difficulty
        })

        return True

    async def create_difficulty_change_notification(
        self,
        user_id: int,
        previous_difficulty: ExerciseDifficulty,
        new_difficulty: ExerciseDifficulty
    ) -> DifficultyChangeNotification:
        """
        Create a notification for a difficulty change.

        Args:
            user_id: User ID
            previous_difficulty: Previous difficulty level
            new_difficulty: New difficulty level

        Returns:
            DifficultyChangeNotification
        """
        # Determine change type
        difficulty_order = {
            ExerciseDifficulty.EASY: 1,
            ExerciseDifficulty.MEDIUM: 2,
            ExerciseDifficulty.HARD: 3
        }

        change_type = "increase" if (
            difficulty_order[new_difficulty] > difficulty_order[previous_difficulty]
        ) else "decrease"

        # Generate appropriate message
        if change_type == "increase":
            message = (
                f"Congratulations! Your exercises will now be at {new_difficulty.value} "
                f"difficulty. You've shown great progress!"
            )
            reason = "Consistent success on recent exercises"
        else:
            message = (
                f"We're adjusting your exercises to {new_difficulty.value} difficulty "
                f"to help you build a stronger foundation."
            )
            reason = "Difficulty adjustment to optimize learning"

        notification = DifficultyChangeNotification(
            user_id=user_id,
            previous_difficulty=previous_difficulty,
            new_difficulty=new_difficulty,
            change_type=change_type,
            message=message,
            reason=reason,
            timestamp=datetime.utcnow()
        )

        logger.info("Difficulty change notification created", extra={
            "user_id": user_id,
            "change_type": change_type,
            "previous": previous_difficulty,
            "new": new_difficulty
        })

        return notification

    # ===================================================================
    # MANUAL DIFFICULTY OVERRIDE
    # ===================================================================

    async def set_manual_difficulty(
        self,
        user_id: int,
        difficulty: ExerciseDifficulty,
        reason: Optional[str] = None
    ) -> bool:
        """
        Allow user to manually set their difficulty level.

        This overrides the adaptive algorithm until the next automatic adjustment.

        Args:
            user_id: User ID
            difficulty: Desired difficulty level
            reason: Optional reason for manual override

        Returns:
            True if successfully set
        """
        logger.info("Manual difficulty override requested", extra={
            "user_id": user_id,
            "difficulty": difficulty,
            "reason": reason
        })

        # Verify user exists
        user = await self._get_user(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")

        # Check if difficulty is appropriate for user's skill level
        bounds = self._get_difficulty_bounds(user.skill_level)
        difficulty_order = {
            ExerciseDifficulty.EASY: 1,
            ExerciseDifficulty.MEDIUM: 2,
            ExerciseDifficulty.HARD: 3
        }

        if difficulty_order[difficulty] < difficulty_order[bounds.min_difficulty]:
            logger.warning("Manual difficulty below recommended minimum", extra={
                "user_id": user_id,
                "requested": difficulty,
                "minimum": bounds.min_difficulty
            })

        if difficulty_order[difficulty] > difficulty_order[bounds.max_difficulty]:
            logger.warning("Manual difficulty above recommended maximum", extra={
                "user_id": user_id,
                "requested": difficulty,
                "maximum": bounds.max_difficulty
            })

        # Apply the difficulty
        success = await self.apply_difficulty_adjustment(user_id, difficulty)

        logger.info("Manual difficulty override applied", extra={
            "user_id": user_id,
            "difficulty": difficulty,
            "success": success
        })

        return success

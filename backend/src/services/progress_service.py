"""
Progress Service - Business logic for progress tracking and achievements.

This service handles:
- Progress metrics calculation and retrieval
- Achievement tracking and unlocking
- Streak calculation and maintenance
- Performance statistics aggregation
- Progress history tracking
- Badge assignment
- Skill level progression
- Progress data export
"""
from datetime import datetime, timedelta, date
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
import csv
import io

from src.models.user import User
from src.models.exercise import UserExercise, ExerciseStatus
from src.models.achievement import (
    Achievement,
    UserAchievement,
    ProgressSnapshot,
    SkillLevel,
    AchievementCategory
)
from src.logging_config import get_logger

logger = get_logger(__name__)


class ProgressService:
    """Service for managing user progress tracking and achievements."""

    def __init__(self, session: AsyncSession):
        """
        Initialize progress service.

        Args:
            session: Database session
        """
        self.session = session

    # ===================================================================
    # PROGRESS METRICS
    # ===================================================================

    async def get_user_progress_metrics(self, user_id: int) -> Dict[str, Any]:
        """
        Get comprehensive progress metrics for a user.

        Args:
            user_id: User ID

        Returns:
            Dictionary with progress metrics
        """
        logger.info("Getting progress metrics for user", extra={"user_id": user_id})

        # Get user
        user = await self._get_user(user_id)

        # Get completed exercises statistics
        stats = await self._calculate_user_statistics(user_id)

        # Get achievements
        achievements = await self._get_user_achievements_with_progress(user_id)

        # Get skill levels
        skill_levels = await self._get_user_skill_levels(user_id)

        return {
            "exercises_completed": user.exercises_completed,
            "current_streak": user.current_streak,
            "longest_streak": user.longest_streak,
            "total_time_spent_seconds": stats.get("total_time_spent", 0),
            "average_grade": stats.get("average_grade"),
            "achievements": achievements,
            "skill_levels": skill_levels
        }

    async def _get_user(self, user_id: int) -> User:
        """Get user by ID."""
        stmt = select(User).where(User.id == user_id)
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            raise ValueError(f"User {user_id} not found")

        return user

    async def _calculate_user_statistics(self, user_id: int) -> Dict[str, Any]:
        """Calculate aggregate statistics for user's completed exercises."""
        stmt = select(
            func.sum(UserExercise.time_spent_seconds).label("total_time"),
            func.avg(UserExercise.grade).label("avg_grade"),
            func.count(UserExercise.id).label("count")
        ).where(
            and_(
                UserExercise.user_id == user_id,
                UserExercise.status == ExerciseStatus.COMPLETED
            )
        )

        result = await self.session.execute(stmt)
        row = result.one_or_none()

        if not row:
            return {"total_time_spent": 0, "average_grade": None}

        return {
            "total_time_spent": row.total_time or 0,
            "average_grade": float(row.avg_grade) if row.avg_grade else None
        }

    async def _get_user_skill_levels(self, user_id: int) -> Dict[str, Any]:
        """Get all skill levels for user organized by topic."""
        stmt = select(SkillLevel).where(SkillLevel.user_id == user_id)
        result = await self.session.execute(stmt)
        skill_levels = result.scalars().all()

        # Convert to dictionary keyed by topic
        levels_dict = {}
        for skill in skill_levels:
            levels_dict[skill.topic] = {
                "level": skill.level,
                "exercises_completed": skill.exercises_completed,
                "average_grade": skill.average_grade,
                "updated_at": skill.level_updated_at
            }

        return levels_dict

    # ===================================================================
    # ACHIEVEMENT TRACKING
    # ===================================================================

    async def get_user_achievements(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Get all achievements with user's progress and unlock status.

        Args:
            user_id: User ID

        Returns:
            List of achievements with progress
        """
        logger.info("Getting achievements for user", extra={"user_id": user_id})

        return await self._get_user_achievements_with_progress(user_id)

    async def _get_user_achievements_with_progress(self, user_id: int) -> List[Dict[str, Any]]:
        """Get achievements with user progress and unlock status."""
        # Get all achievements
        stmt = select(Achievement).where(Achievement.is_active == True).order_by(
            Achievement.category,
            Achievement.requirement_value
        )
        result = await self.session.execute(stmt)
        all_achievements = result.scalars().all()

        # Get user's achievement records
        stmt = select(UserAchievement).where(UserAchievement.user_id == user_id)
        result = await self.session.execute(stmt)
        user_achievements = {ua.achievement_id: ua for ua in result.scalars().all()}

        # Get user for current progress
        user = await self._get_user(user_id)

        achievements_list = []
        for achievement in all_achievements:
            user_achievement = user_achievements.get(achievement.id)

            # Calculate current progress based on achievement category
            current_value = self._get_current_metric_value(user, achievement)

            # Build achievement response
            ach_dict = {
                "id": achievement.id,
                "name": achievement.name,
                "slug": achievement.slug,
                "title": achievement.title,
                "description": achievement.description,
                "category": achievement.category.value,
                "requirement_value": achievement.requirement_value,
                "requirement_description": achievement.requirement_description,
                "icon_url": achievement.icon_url,
                "badge_color": achievement.badge_color,
                "points": achievement.points,
                "type": achievement.slug,  # For test compatibility
            }

            if user_achievement and user_achievement.earned:
                ach_dict["unlocked"] = True
                ach_dict["unlocked_at"] = user_achievement.earned_at
                ach_dict["progress"] = achievement.requirement_value
                ach_dict["target"] = achievement.requirement_value
                ach_dict["progress_percentage"] = 100.0
            else:
                ach_dict["unlocked"] = False
                ach_dict["unlocked_at"] = None
                ach_dict["progress"] = current_value
                ach_dict["target"] = achievement.requirement_value
                ach_dict["progress_percentage"] = (
                    (current_value / achievement.requirement_value * 100.0)
                    if achievement.requirement_value > 0 else 0.0
                )

            achievements_list.append(ach_dict)

        return achievements_list

    def _get_current_metric_value(self, user: User, achievement: Achievement) -> int:
        """Get current value of metric for achievement."""
        category = achievement.category

        if category == AchievementCategory.STREAK:
            return user.current_streak
        elif category == AchievementCategory.EXERCISE:
            return user.exercises_completed
        elif category == AchievementCategory.GITHUB:
            # Future: track GitHub reviews
            return 0
        elif category == AchievementCategory.COMMUNITY:
            # Future: track community participation
            return 0
        elif category == AchievementCategory.SKILL:
            # Future: track skill mastery
            return 0
        else:
            return 0

    async def check_and_unlock_achievements(self, user_id: int) -> List[str]:
        """
        Check if user has met criteria for any new achievements and unlock them.

        Args:
            user_id: User ID

        Returns:
            List of newly unlocked achievement slugs
        """
        logger.info("Checking achievements for user", extra={"user_id": user_id})

        user = await self._get_user(user_id)
        newly_unlocked = []

        # Get all active achievements
        stmt = select(Achievement).where(Achievement.is_active == True)
        result = await self.session.execute(stmt)
        all_achievements = result.scalars().all()

        # Get user's existing achievement records
        stmt = select(UserAchievement).where(UserAchievement.user_id == user_id)
        result = await self.session.execute(stmt)
        user_achievements = {ua.achievement_id: ua for ua in result.scalars().all()}

        for achievement in all_achievements:
            # Skip if already earned
            if achievement.id in user_achievements and user_achievements[achievement.id].earned:
                continue

            # Check if criteria met
            current_value = self._get_current_metric_value(user, achievement)

            if current_value >= achievement.requirement_value:
                # Unlock achievement
                if achievement.id in user_achievements:
                    # Update existing record
                    user_ach = user_achievements[achievement.id]
                    user_ach.earned = True
                    user_ach.earned_at = datetime.utcnow()
                    user_ach.progress_current = current_value
                else:
                    # Create new record
                    user_ach = UserAchievement(
                        user_id=user_id,
                        achievement_id=achievement.id,
                        earned=True,
                        earned_at=datetime.utcnow(),
                        progress_current=current_value,
                        progress_target=achievement.requirement_value
                    )
                    self.session.add(user_ach)

                newly_unlocked.append(achievement.slug)
                logger.info("Achievement unlocked", extra={
                    "user_id": user_id,
                    "achievement": achievement.slug
                })

        await self.session.flush()
        return newly_unlocked

    # ===================================================================
    # STREAK TRACKING
    # ===================================================================

    async def update_streak(
        self,
        user_id: int,
        completed_today: bool,
        user_timezone: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update user's streak based on exercise completion.

        Args:
            user_id: User ID
            completed_today: Whether user completed exercise today
            user_timezone: User's timezone (for future enhancement)

        Returns:
            Dictionary with streak update results
        """
        logger.info("Updating streak for user", extra={"user_id": user_id})

        user = await self._get_user(user_id)

        # Calculate streak
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        streak_maintained = False
        streak_broken = False
        previous_streak = user.current_streak
        new_record = False

        if user.last_exercise_date is None:
            # First ever exercise
            if completed_today:
                user.current_streak = 1
                streak_maintained = True
        else:
            # Calculate days since last exercise
            days_since = (now - user.last_exercise_date).days

            if days_since == 0:
                # Completed today already (same day)
                streak_maintained = True
            elif days_since == 1:
                # Completed yesterday, increment streak
                if completed_today:
                    user.current_streak += 1
                    streak_maintained = True
            else:
                # Missed days, streak broken
                streak_broken = True
                previous_streak = user.current_streak
                user.current_streak = 1 if completed_today else 0
                logger.info("Streak broken", extra={
                    "user_id": user_id,
                    "previous_streak": previous_streak,
                    "days_missed": days_since - 1
                })

        # Update longest streak if needed
        if user.current_streak > user.longest_streak:
            user.longest_streak = user.current_streak
            new_record = True
            logger.info("New streak record", extra={
                "user_id": user_id,
                "streak": user.current_streak
            })

        # Update last exercise date
        if completed_today:
            user.last_exercise_date = now

        await self.session.flush()

        # Check for streak achievements
        achievements = await self.check_and_unlock_achievements(user_id)

        return {
            "current_streak": user.current_streak,
            "longest_streak": user.longest_streak,
            "streak_maintained": streak_maintained,
            "streak_broken": streak_broken,
            "previous_streak": previous_streak if streak_broken else None,
            "new_record": new_record,
            "achievements_unlocked": achievements
        }

    # ===================================================================
    # PERFORMANCE STATISTICS
    # ===================================================================

    async def get_performance_statistics(
        self,
        user_id: int,
        period: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get performance statistics for user.

        Args:
            user_id: User ID
            period: Time period filter (daily, weekly, monthly, all)

        Returns:
            Dictionary with statistics
        """
        logger.info("Getting performance statistics", extra={
            "user_id": user_id,
            "period": period
        })

        # Determine date range
        date_filter = self._get_date_filter_for_period(period)

        # Base query for completed exercises
        base_conditions = [
            UserExercise.user_id == user_id,
            UserExercise.status == ExerciseStatus.COMPLETED
        ]

        if date_filter:
            base_conditions.append(UserExercise.completed_at >= date_filter)

        # Average grade
        stmt = select(func.avg(UserExercise.grade)).where(and_(*base_conditions))
        result = await self.session.execute(stmt)
        avg_grade = result.scalar() or 0.0

        # Average time per exercise
        stmt = select(func.avg(UserExercise.time_spent_seconds)).where(and_(*base_conditions))
        result = await self.session.execute(stmt)
        avg_time = result.scalar() or 0.0

        # Total hints requested
        stmt = select(func.sum(UserExercise.hints_requested)).where(and_(*base_conditions))
        result = await self.session.execute(stmt)
        total_hints = result.scalar() or 0

        # Get exercises with details for categorization
        stmt = select(UserExercise).where(and_(*base_conditions))
        result = await self.session.execute(stmt)
        exercises = result.scalars().all()

        # For now, return empty dicts for difficulty/type (would need join with Exercise table)
        exercises_by_difficulty = {}
        exercises_by_type = {}

        # Recent performance trend (last 7 days)
        recent_trend = await self._get_recent_performance_trend(user_id, days=7)

        return {
            "average_grade": float(avg_grade),
            "average_time_per_exercise": float(avg_time),
            "total_hints_requested": int(total_hints),
            "exercises_by_difficulty": exercises_by_difficulty,
            "exercises_by_type": exercises_by_type,
            "recent_performance_trend": recent_trend,
            "period": period
        }

    def _get_date_filter_for_period(self, period: Optional[str]) -> Optional[datetime]:
        """Get datetime filter for given period."""
        if not period or period == "all":
            return None

        now = datetime.utcnow()

        if period == "daily":
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "weekly":
            return now - timedelta(days=7)
        elif period == "monthly":
            return now - timedelta(days=30)
        else:
            return None

    async def _get_recent_performance_trend(self, user_id: int, days: int = 7) -> List[Dict[str, Any]]:
        """Get recent performance trend data points."""
        start_date = datetime.utcnow() - timedelta(days=days)

        stmt = select(
            func.date(UserExercise.completed_at).label("date"),
            func.count(UserExercise.id).label("count"),
            func.avg(UserExercise.grade).label("avg_grade")
        ).where(
            and_(
                UserExercise.user_id == user_id,
                UserExercise.status == ExerciseStatus.COMPLETED,
                UserExercise.completed_at >= start_date
            )
        ).group_by(
            func.date(UserExercise.completed_at)
        ).order_by(
            func.date(UserExercise.completed_at)
        )

        result = await self.session.execute(stmt)
        rows = result.all()

        trend = []
        for row in rows:
            trend.append({
                "date": str(row.date),
                "exercises_completed": row.count,
                "average_grade": float(row.avg_grade) if row.avg_grade else None
            })

        return trend

    # ===================================================================
    # PROGRESS HISTORY
    # ===================================================================

    async def get_progress_history(
        self,
        user_id: int,
        days: Optional[int] = 30,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Get historical progress data.

        Args:
            user_id: User ID
            days: Number of days of history
            start_date: Custom start date
            end_date: Custom end date

        Returns:
            Dictionary with history data
        """
        logger.info("Getting progress history", extra={
            "user_id": user_id,
            "days": days
        })

        # Determine date range
        if start_date and end_date:
            filter_start = datetime.combine(start_date, datetime.min.time())
            filter_end = datetime.combine(end_date, datetime.max.time())
        else:
            filter_end = datetime.utcnow()
            filter_start = filter_end - timedelta(days=days or 30)

        # Get progress snapshots
        stmt = select(ProgressSnapshot).where(
            and_(
                ProgressSnapshot.user_id == user_id,
                ProgressSnapshot.snapshot_date >= filter_start,
                ProgressSnapshot.snapshot_date <= filter_end
            )
        ).order_by(ProgressSnapshot.snapshot_date)

        result = await self.session.execute(stmt)
        snapshots = result.scalars().all()

        history = []
        for snapshot in snapshots:
            history.append({
                "date": snapshot.snapshot_date,
                "exercises_completed": snapshot.exercises_completed_today,
                "time_spent_seconds": snapshot.time_spent_today_seconds,
                "average_grade": snapshot.average_grade_today,
                "streak": snapshot.current_streak,
                "achievements_unlocked": snapshot.achievements_unlocked_today
            })

        return {
            "history": history,
            "start_date": filter_start.date(),
            "end_date": filter_end.date(),
            "total_days": len(history)
        }

    # ===================================================================
    # BADGES
    # ===================================================================

    async def get_user_badges(self, user_id: int) -> Dict[str, Any]:
        """
        Get user's badges (earned and available).

        Args:
            user_id: User ID

        Returns:
            Dictionary with badges
        """
        logger.info("Getting badges for user", extra={"user_id": user_id})

        # Get all achievements (which are badges)
        achievements = await self._get_user_achievements_with_progress(user_id)

        # Format as badges
        badges = []
        for ach in achievements:
            badge = {
                "id": ach["id"],
                "type": ach["slug"],
                "name": ach["title"],
                "description": ach["description"],
                "icon_url": ach.get("icon_url"),
                "earned": ach["unlocked"],
                "category": ach["category"],
                "points": ach["points"]
            }

            if ach["unlocked"]:
                badge["earned_at"] = ach["unlocked_at"]

            badges.append(badge)

        # Count earned badges
        total_earned = sum(1 for b in badges if b["earned"])
        points_earned = sum(b["points"] for b in badges if b["earned"])

        return {
            "badges": badges,
            "total_earned": total_earned,
            "total_available": len(badges),
            "points_earned": points_earned
        }

    # ===================================================================
    # SKILL LEVELS
    # ===================================================================

    async def get_skill_levels(self, user_id: int) -> Dict[str, Any]:
        """
        Get user's skill levels across all topics.

        Args:
            user_id: User ID

        Returns:
            Dictionary with skill levels
        """
        logger.info("Getting skill levels for user", extra={"user_id": user_id})

        stmt = select(SkillLevel).where(SkillLevel.user_id == user_id)
        result = await self.session.execute(stmt)
        skill_levels = result.scalars().all()

        levels_list = []
        for skill in skill_levels:
            levels_list.append({
                "topic": skill.topic,
                "level": skill.level,
                "exercises_completed": skill.exercises_completed,
                "average_grade": skill.average_grade,
                "total_time_spent_seconds": skill.total_time_spent_seconds,
                "level_updated_at": skill.level_updated_at,
                "previous_level": skill.previous_level
            })

        return {"skill_levels": levels_list}

    async def calculate_skill_level(self, user_id: int, topic: str) -> Dict[str, Any]:
        """
        Calculate and update skill level for a topic.

        Args:
            user_id: User ID
            topic: Topic to calculate for

        Returns:
            Dictionary with calculation results
        """
        logger.info("Calculating skill level", extra={
            "user_id": user_id,
            "topic": topic
        })

        # Get or create skill level record
        stmt = select(SkillLevel).where(
            and_(
                SkillLevel.user_id == user_id,
                SkillLevel.topic == topic
            )
        )
        result = await self.session.execute(stmt)
        skill_level = result.scalar_one_or_none()

        if not skill_level:
            skill_level = SkillLevel(
                user_id=user_id,
                topic=topic,
                level="beginner",
                exercises_completed=0
            )
            self.session.add(skill_level)
            await self.session.flush()

        previous_level = skill_level.level

        # Calculate new level based on performance
        # Simple logic: beginner (0-9), intermediate (10-29), advanced (30-49), expert (50+)
        exercises = skill_level.exercises_completed
        avg_grade = skill_level.average_grade or 0

        if exercises >= 50 and avg_grade >= 80:
            new_level = "expert"
        elif exercises >= 30 and avg_grade >= 70:
            new_level = "advanced"
        elif exercises >= 10 and avg_grade >= 60:
            new_level = "intermediate"
        else:
            new_level = "beginner"

        level_changed = new_level != previous_level

        if level_changed:
            skill_level.previous_level = previous_level
            skill_level.level = new_level
            skill_level.level_updated_at = datetime.utcnow()
            await self.session.flush()

        # Determine next level
        level_order = ["beginner", "intermediate", "advanced", "expert"]
        current_index = level_order.index(new_level)
        next_level = level_order[current_index + 1] if current_index < len(level_order) - 1 else None

        return {
            "topic": topic,
            "current_level": new_level,
            "previous_level": previous_level if level_changed else None,
            "level_changed": level_changed,
            "exercises_completed": exercises,
            "average_grade": avg_grade,
            "next_level": next_level,
            "progress_to_next": None  # Future enhancement
        }

    # ===================================================================
    # EXPORT
    # ===================================================================

    async def export_progress_data(
        self,
        user_id: int,
        format: str = "json"
    ) -> Any:
        """
        Export user's progress data.

        Args:
            user_id: User ID
            format: Export format (json or csv)

        Returns:
            Export data in requested format
        """
        logger.info("Exporting progress data", extra={
            "user_id": user_id,
            "format": format
        })

        if format == "json":
            return await self._export_json(user_id)
        elif format == "csv":
            return await self._export_csv(user_id)
        else:
            raise ValueError(f"Unsupported export format: {format}")

    async def _export_json(self, user_id: int) -> Dict[str, Any]:
        """Export progress data as JSON."""
        # Get all data
        metrics = await self.get_user_progress_metrics(user_id)
        achievements = await self.get_user_achievements(user_id)
        statistics = await self.get_performance_statistics(user_id, period="all")
        history = await self.get_progress_history(user_id, days=365)

        return {
            "user_id": user_id,
            "export_date": datetime.utcnow(),
            "progress_metrics": metrics,
            "achievements": achievements,
            "exercise_history": history["history"],
            "statistics": statistics
        }

    async def _export_csv(self, user_id: int) -> str:
        """Export exercise history as CSV."""
        # Get exercise history
        stmt = select(UserExercise).where(
            and_(
                UserExercise.user_id == user_id,
                UserExercise.status == ExerciseStatus.COMPLETED
            )
        ).order_by(UserExercise.completed_at)

        result = await self.session.execute(stmt)
        exercises = result.scalars().all()

        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([
            "exercise_id",
            "completed_at",
            "grade",
            "time_spent_seconds",
            "hints_requested",
            "test_cases_passed",
            "test_cases_total"
        ])

        # Data rows
        for exercise in exercises:
            writer.writerow([
                exercise.exercise_id,
                exercise.completed_at.isoformat() if exercise.completed_at else "",
                exercise.grade or "",
                exercise.time_spent_seconds or "",
                exercise.hints_requested,
                exercise.test_cases_passed or "",
                exercise.test_cases_total or ""
            ])

        return output.getvalue()

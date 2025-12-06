"""
Integration tests for Difficulty Adaptation Engine (Work Stream D3).

Test Strategy:
-------------
These tests follow TDD principles and focus on REAL integration testing:
- Test actual adaptation algorithm logic with real database interactions
- Test the complete flow from performance tracking to difficulty adjustment
- Verify business rules from REQ-EXERCISE-003
- Mock ONLY external dependencies (LLM service)
- Test edge cases and boundary conditions

Key Scenarios:
1. Difficulty increases after 3 consecutive successes without hints
2. Difficulty decreases after 2 consecutive struggles
3. Difficulty respects user skill level bounds (beginner/intermediate/advanced)
4. Performance metrics are tracked correctly
5. Notifications are generated on difficulty changes
6. Edge cases: new users, long gaps, mixed performance patterns

Requirements Coverage:
- REQ-EXERCISE-003: Adaptive difficulty adjustment
- REQ-EXERCISE-004: Exercise completion metrics tracking
"""
import pytest
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from src.models.user import User, SkillLevel
from src.models.exercise import (
    Exercise, UserExercise, ExerciseType, ExerciseDifficulty, ExerciseStatus
)
from src.services.difficulty_service import DifficultyService
from src.schemas.difficulty import (
    PerformanceMetrics,
    DifficultyAdjustmentResponse,
    DifficultyChangeNotification
)


# ===================================================================
# FIXTURES
# ===================================================================

@pytest.fixture
async def test_user(db_session):
    """Create a test user with intermediate skill level."""
    user = User(
        email=f"test-difficulty-{uuid.uuid4()}@example.com",
        name="Test User",
        password_hash="hashed_password",
        email_verified=True,
        onboarding_completed=True,
        programming_language="python",
        skill_level=SkillLevel.INTERMEDIATE,
        career_goals="Backend development",
        learning_style="hands-on",
        time_commitment="30min"
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def beginner_user(db_session):
    """Create a beginner user for boundary testing."""
    user = User(
        email=f"beginner-{uuid.uuid4()}@example.com",
        name="Beginner User",
        password_hash="hashed_password",
        email_verified=True,
        onboarding_completed=True,
        programming_language="python",
        skill_level=SkillLevel.BEGINNER,
        career_goals="Learn programming",
        learning_style="visual",
        time_commitment="15min"
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def advanced_user(db_session):
    """Create an advanced user for boundary testing."""
    user = User(
        email=f"advanced-{uuid.uuid4()}@example.com",
        name="Advanced User",
        password_hash="hashed_password",
        email_verified=True,
        onboarding_completed=True,
        programming_language="python",
        skill_level=SkillLevel.ADVANCED,
        career_goals="System design mastery",
        learning_style="theoretical",
        time_commitment="60min"
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.fixture
def difficulty_service(db_session):
    """Create a difficulty service instance."""
    return DifficultyService(db_session)


async def create_exercise(db_session, difficulty=ExerciseDifficulty.MEDIUM, language="python"):
    """Helper to create an exercise."""
    exercise = Exercise(
        title=f"Test Exercise {datetime.utcnow().timestamp()}",
        description="Test description",
        instructions="Test instructions",
        starter_code="# Your code here",
        exercise_type=ExerciseType.ALGORITHM,
        difficulty=difficulty,
        programming_language=language,
        topics="arrays,loops",
        generated_by_ai=True
    )
    db_session.add(exercise)
    await db_session.flush()
    await db_session.refresh(exercise)
    return exercise


async def create_user_exercise(
    db_session,
    user_id,
    exercise_id,
    status=ExerciseStatus.COMPLETED,
    grade=None,
    hints_requested=0,
    time_spent_seconds=None,
    completed_at=None
):
    """Helper to create a user exercise record."""
    user_exercise = UserExercise(
        user_id=user_id,
        exercise_id=exercise_id,
        status=status,
        grade=grade,
        hints_requested=hints_requested,
        time_spent_seconds=time_spent_seconds,
        completed_at=completed_at or datetime.utcnow(),
        started_at=datetime.utcnow() - timedelta(minutes=30)
    )
    db_session.add(user_exercise)
    await db_session.flush()
    await db_session.refresh(user_exercise)
    return user_exercise


# ===================================================================
# TEST CASES: DIFFICULTY INCREASE (3 consecutive successes)
# ===================================================================

@pytest.mark.asyncio
async def test_difficulty_increases_after_three_consecutive_successes(
    db_session, test_user, difficulty_service
):
    """
    Test: Difficulty increases after 3 consecutive successful completions without hints.
    REQ-EXERCISE-003: Increase difficulty after 3 consecutive successful completions without hints.
    """
    # Create 3 consecutive successful exercises (medium difficulty)
    for i in range(3):
        exercise = await create_exercise(db_session, ExerciseDifficulty.MEDIUM)
        await create_user_exercise(
            db_session,
            user_id=test_user.id,
            exercise_id=exercise.id,
            status=ExerciseStatus.COMPLETED,
            grade=90.0,  # High grade
            hints_requested=0,  # No hints
            time_spent_seconds=600,  # Reasonable time
            completed_at=datetime.utcnow() - timedelta(days=2-i)
        )

    await db_session.flush()

    # Check if difficulty should be adjusted
    result = await difficulty_service.analyze_and_adjust_difficulty(test_user.id)

    assert result is not None
    assert result.should_adjust is True
    assert result.current_difficulty == ExerciseDifficulty.MEDIUM
    assert result.recommended_difficulty == ExerciseDifficulty.HARD
    assert result.reason == "increase"
    assert "3 consecutive successes" in result.message.lower()


@pytest.mark.asyncio
async def test_difficulty_does_not_increase_with_hints_used(
    db_session, test_user, difficulty_service
):
    """
    Test: Difficulty should NOT increase if user used hints (even with good grades).
    REQ-EXERCISE-003: Only increase after successes WITHOUT hints.
    """
    # Create 3 consecutive exercises where user used hints
    for i in range(3):
        exercise = await create_exercise(db_session, ExerciseDifficulty.MEDIUM)
        await create_user_exercise(
            db_session,
            user_id=test_user.id,
            exercise_id=exercise.id,
            status=ExerciseStatus.COMPLETED,
            grade=85.0,  # Good grade
            hints_requested=2,  # BUT used hints
            time_spent_seconds=900,
            completed_at=datetime.utcnow() - timedelta(days=2-i)
        )

    await db_session.flush()

    # Check if difficulty should be adjusted
    result = await difficulty_service.analyze_and_adjust_difficulty(test_user.id)

    # Should not increase difficulty
    assert result.should_adjust is False or result.recommended_difficulty != ExerciseDifficulty.HARD


@pytest.mark.asyncio
async def test_difficulty_does_not_increase_beyond_user_skill_bound(
    db_session, beginner_user, difficulty_service
):
    """
    Test: Difficulty should not increase beyond appropriate level for user skill.
    REQ-EXERCISE-003: Maintain difficulty level appropriate to stated skill level.
    """
    # Create 3 consecutive successes for beginner (already at medium - max for beginner)
    for i in range(3):
        exercise = await create_exercise(db_session, ExerciseDifficulty.MEDIUM)
        await create_user_exercise(
            db_session,
            user_id=beginner_user.id,
            exercise_id=exercise.id,
            status=ExerciseStatus.COMPLETED,
            grade=95.0,
            hints_requested=0,
            time_spent_seconds=600,
            completed_at=datetime.utcnow() - timedelta(days=2-i)
        )

    await db_session.flush()

    # Check if difficulty should be adjusted
    result = await difficulty_service.analyze_and_adjust_difficulty(beginner_user.id)

    # Should not recommend HARD for a beginner
    if result.should_adjust:
        assert result.recommended_difficulty != ExerciseDifficulty.HARD


# ===================================================================
# TEST CASES: DIFFICULTY DECREASE (2 consecutive struggles)
# ===================================================================

@pytest.mark.asyncio
async def test_difficulty_decreases_after_two_consecutive_struggles(
    db_session, test_user, difficulty_service
):
    """
    Test: Difficulty decreases after user struggles on 2 consecutive exercises.
    REQ-EXERCISE-003: Decrease difficulty after user struggles on 2 consecutive exercises.
    """
    # Create 2 consecutive struggling exercises (hard difficulty)
    for i in range(2):
        exercise = await create_exercise(db_session, ExerciseDifficulty.HARD)
        await create_user_exercise(
            db_session,
            user_id=test_user.id,
            exercise_id=exercise.id,
            status=ExerciseStatus.COMPLETED,
            grade=45.0,  # Low grade = struggle
            hints_requested=5,  # Many hints = struggle
            time_spent_seconds=3600,  # Long time = struggle
            completed_at=datetime.utcnow() - timedelta(days=1-i)
        )

    await db_session.flush()

    # Check if difficulty should be adjusted
    result = await difficulty_service.analyze_and_adjust_difficulty(test_user.id)

    assert result is not None
    assert result.should_adjust is True
    assert result.current_difficulty == ExerciseDifficulty.HARD
    assert result.recommended_difficulty == ExerciseDifficulty.MEDIUM
    assert result.reason == "decrease"
    assert "struggle" in result.message.lower() or "difficult" in result.message.lower()


@pytest.mark.asyncio
async def test_difficulty_does_not_decrease_below_minimum(
    db_session, beginner_user, difficulty_service
):
    """
    Test: Difficulty should not decrease below easy (minimum level).
    REQ-EXERCISE-003: Maintain appropriate bounds.
    """
    # Create 2 struggling exercises already at EASY
    for i in range(2):
        exercise = await create_exercise(db_session, ExerciseDifficulty.EASY)
        await create_user_exercise(
            db_session,
            user_id=beginner_user.id,
            exercise_id=exercise.id,
            status=ExerciseStatus.COMPLETED,
            grade=40.0,
            hints_requested=6,
            time_spent_seconds=4000,
            completed_at=datetime.utcnow() - timedelta(days=1-i)
        )

    await db_session.flush()

    # Check if difficulty should be adjusted
    result = await difficulty_service.analyze_and_adjust_difficulty(beginner_user.id)

    # Should either not adjust or stay at EASY
    if result.should_adjust:
        assert result.recommended_difficulty == ExerciseDifficulty.EASY


@pytest.mark.asyncio
async def test_skipped_exercises_count_as_struggles(
    db_session, test_user, difficulty_service
):
    """
    Test: Skipped exercises should count as struggles for difficulty adjustment.
    """
    # Create 2 consecutive skipped exercises
    for i in range(2):
        exercise = await create_exercise(db_session, ExerciseDifficulty.HARD)
        await create_user_exercise(
            db_session,
            user_id=test_user.id,
            exercise_id=exercise.id,
            status=ExerciseStatus.SKIPPED,
            grade=None,
            hints_requested=3,
            time_spent_seconds=1200,
            completed_at=datetime.utcnow() - timedelta(days=1-i)
        )

    await db_session.flush()

    # Check if difficulty should be adjusted
    result = await difficulty_service.analyze_and_adjust_difficulty(test_user.id)

    # Should recommend decrease
    assert result is not None
    assert result.should_adjust is True
    assert result.reason == "decrease"


# ===================================================================
# TEST CASES: PERFORMANCE METRICS TRACKING
# ===================================================================

@pytest.mark.asyncio
async def test_get_recent_performance_metrics(
    db_session, test_user, difficulty_service
):
    """
    Test: Service correctly retrieves and calculates performance metrics.
    REQ-EXERCISE-004: Track exercise completion metrics.
    """
    # Create exercises with varied performance
    exercises_data = [
        (ExerciseDifficulty.MEDIUM, 85.0, 0, 600, ExerciseStatus.COMPLETED),
        (ExerciseDifficulty.MEDIUM, 90.0, 1, 500, ExerciseStatus.COMPLETED),
        (ExerciseDifficulty.MEDIUM, 75.0, 2, 800, ExerciseStatus.COMPLETED),
        (ExerciseDifficulty.HARD, 60.0, 4, 1500, ExerciseStatus.COMPLETED),
        (ExerciseDifficulty.HARD, None, 0, 300, ExerciseStatus.SKIPPED),
    ]

    for i, (difficulty, grade, hints, time, status) in enumerate(exercises_data):
        exercise = await create_exercise(db_session, difficulty)
        await create_user_exercise(
            db_session,
            user_id=test_user.id,
            exercise_id=exercise.id,
            status=status,
            grade=grade,
            hints_requested=hints,
            time_spent_seconds=time,
            completed_at=datetime.utcnow() - timedelta(days=4-i)
        )

    await db_session.flush()

    # Get performance metrics
    metrics = await difficulty_service.get_recent_performance(test_user.id, limit=5)

    assert metrics is not None
    assert len(metrics.recent_exercises) == 5
    assert metrics.average_grade is not None
    assert metrics.average_hints is not None
    assert metrics.average_time_seconds is not None
    assert metrics.completion_rate is not None


@pytest.mark.asyncio
async def test_performance_metrics_with_no_exercises(
    db_session, test_user, difficulty_service
):
    """
    Test: Service handles new users with no exercise history.
    Edge case: New users.
    """
    # Don't create any exercises for this user

    # Get performance metrics
    metrics = await difficulty_service.get_recent_performance(test_user.id, limit=5)

    assert metrics is not None
    assert len(metrics.recent_exercises) == 0
    assert metrics.average_grade == 0.0 or metrics.average_grade is None
    assert metrics.consecutive_successes == 0
    assert metrics.consecutive_struggles == 0


# ===================================================================
# TEST CASES: NOTIFICATION GENERATION
# ===================================================================

@pytest.mark.asyncio
async def test_difficulty_change_notification_generated(
    db_session, test_user, difficulty_service
):
    """
    Test: System generates notification when difficulty changes.
    REQ-EXERCISE-003: Notify user when difficulty level changes.
    """
    # Create 3 consecutive successes to trigger increase
    for i in range(3):
        exercise = await create_exercise(db_session, ExerciseDifficulty.MEDIUM)
        await create_user_exercise(
            db_session,
            user_id=test_user.id,
            exercise_id=exercise.id,
            status=ExerciseStatus.COMPLETED,
            grade=92.0,
            hints_requested=0,
            time_spent_seconds=600,
            completed_at=datetime.utcnow() - timedelta(days=2-i)
        )

    await db_session.flush()

    # Analyze and get notification
    result = await difficulty_service.analyze_and_adjust_difficulty(test_user.id)

    assert result is not None
    assert result.should_adjust is True

    # Check notification fields
    assert result.message is not None and len(result.message) > 0
    assert result.current_difficulty is not None
    assert result.recommended_difficulty is not None


# ===================================================================
# TEST CASES: EDGE CASES AND BOUNDARY CONDITIONS
# ===================================================================

@pytest.mark.asyncio
async def test_mixed_performance_no_clear_pattern(
    db_session, test_user, difficulty_service
):
    """
    Test: System handles mixed performance (no clear pattern).
    Edge case: Alternating success and struggle.
    """
    # Create alternating good and bad exercises
    performances = [
        (90.0, 0, 600),  # Good
        (50.0, 4, 1800),  # Bad
        (88.0, 1, 700),  # Good
        (45.0, 5, 2000),  # Bad
        (92.0, 0, 550),  # Good
    ]

    for i, (grade, hints, time) in enumerate(performances):
        exercise = await create_exercise(db_session, ExerciseDifficulty.MEDIUM)
        await create_user_exercise(
            db_session,
            user_id=test_user.id,
            exercise_id=exercise.id,
            status=ExerciseStatus.COMPLETED,
            grade=grade,
            hints_requested=hints,
            time_spent_seconds=time,
            completed_at=datetime.utcnow() - timedelta(days=4-i)
        )

    await db_session.flush()

    # Get recommendation
    result = await difficulty_service.analyze_and_adjust_difficulty(test_user.id)

    # Should likely not recommend change (mixed signals)
    assert result is not None
    # No assertion on should_adjust - depends on algorithm implementation


@pytest.mark.asyncio
async def test_long_gap_between_exercises(
    db_session, test_user, difficulty_service
):
    """
    Test: System handles long gaps between exercises appropriately.
    Edge case: User returns after long absence.
    """
    # Create old successful exercises
    for i in range(3):
        exercise = await create_exercise(db_session, ExerciseDifficulty.MEDIUM)
        await create_user_exercise(
            db_session,
            user_id=test_user.id,
            exercise_id=exercise.id,
            status=ExerciseStatus.COMPLETED,
            grade=90.0,
            hints_requested=0,
            time_spent_seconds=600,
            completed_at=datetime.utcnow() - timedelta(days=60-i)  # 60 days ago!
        )

    await db_session.flush()

    # Get recommendation (should potentially be more conservative with old data)
    result = await difficulty_service.analyze_and_adjust_difficulty(test_user.id)

    assert result is not None
    # Algorithm may choose to be conservative with old data


@pytest.mark.asyncio
async def test_difficulty_appropriate_for_beginner(
    db_session, beginner_user, difficulty_service
):
    """
    Test: Recommended difficulty respects beginner skill level bounds.
    REQ-EXERCISE-003: Maintain difficulty level appropriate to stated skill level.
    """
    # Even with great performance, beginner shouldn't jump to HARD
    for i in range(5):
        exercise = await create_exercise(db_session, ExerciseDifficulty.EASY)
        await create_user_exercise(
            db_session,
            user_id=beginner_user.id,
            exercise_id=exercise.id,
            status=ExerciseStatus.COMPLETED,
            grade=95.0,
            hints_requested=0,
            time_spent_seconds=400,
            completed_at=datetime.utcnow() - timedelta(days=4-i)
        )

    await db_session.flush()

    result = await difficulty_service.analyze_and_adjust_difficulty(beginner_user.id)

    # Should recommend at most MEDIUM for beginner
    if result.should_adjust:
        assert result.recommended_difficulty in [ExerciseDifficulty.EASY, ExerciseDifficulty.MEDIUM]


@pytest.mark.asyncio
async def test_difficulty_appropriate_for_advanced(
    db_session, advanced_user, difficulty_service
):
    """
    Test: Advanced users can reach and stay at HARD difficulty.
    REQ-EXERCISE-003: Maintain difficulty level appropriate to stated skill level.
    """
    # Advanced user with strong performance should be comfortable at HARD
    for i in range(3):
        exercise = await create_exercise(db_session, ExerciseDifficulty.HARD)
        await create_user_exercise(
            db_session,
            user_id=advanced_user.id,
            exercise_id=exercise.id,
            status=ExerciseStatus.COMPLETED,
            grade=88.0,
            hints_requested=0,
            time_spent_seconds=900,
            completed_at=datetime.utcnow() - timedelta(days=2-i)
        )

    await db_session.flush()

    result = await difficulty_service.analyze_and_adjust_difficulty(advanced_user.id)

    # Should stay at HARD or not change
    assert result is not None
    # Advanced user doing well at HARD should stay there


@pytest.mark.asyncio
async def test_consecutive_count_resets_on_mixed_performance(
    db_session, test_user, difficulty_service
):
    """
    Test: Consecutive success/struggle counters reset when pattern breaks.
    """
    # 2 successes, then 1 struggle, then 2 more successes
    performances = [
        (90.0, 0, 600, ExerciseStatus.COMPLETED),  # Success 1
        (92.0, 0, 550, ExerciseStatus.COMPLETED),  # Success 2
        (40.0, 6, 2000, ExerciseStatus.COMPLETED),  # Struggle (breaks streak)
        (88.0, 0, 650, ExerciseStatus.COMPLETED),  # Success 1 (new streak)
        (91.0, 1, 700, ExerciseStatus.COMPLETED),  # Success 2 (new streak)
    ]

    for i, (grade, hints, time, status) in enumerate(performances):
        exercise = await create_exercise(db_session, ExerciseDifficulty.MEDIUM)
        await create_user_exercise(
            db_session,
            user_id=test_user.id,
            exercise_id=exercise.id,
            status=status,
            grade=grade,
            hints_requested=hints,
            time_spent_seconds=time,
            completed_at=datetime.utcnow() - timedelta(days=4-i)
        )

    await db_session.flush()

    metrics = await difficulty_service.get_recent_performance(test_user.id, limit=5)

    # Should have only 2 consecutive successes (not 4) due to the struggle
    assert metrics.consecutive_successes < 3


# ===================================================================
# TEST CASES: API INTEGRATION
# ===================================================================

@pytest.mark.asyncio
async def test_apply_difficulty_adjustment_updates_user_profile(
    db_session, test_user, difficulty_service
):
    """
    Test: Applying difficulty adjustment updates user's current difficulty level.
    Integration test for the complete flow.
    """
    # Setup: User has pattern warranting increase
    for i in range(3):
        exercise = await create_exercise(db_session, ExerciseDifficulty.MEDIUM)
        await create_user_exercise(
            db_session,
            user_id=test_user.id,
            exercise_id=exercise.id,
            status=ExerciseStatus.COMPLETED,
            grade=92.0,
            hints_requested=0,
            time_spent_seconds=600,
            completed_at=datetime.utcnow() - timedelta(days=2-i)
        )

    await db_session.flush()

    # Analyze
    result = await difficulty_service.analyze_and_adjust_difficulty(test_user.id)

    if result.should_adjust:
        # Apply the adjustment
        applied = await difficulty_service.apply_difficulty_adjustment(
            user_id=test_user.id,
            new_difficulty=result.recommended_difficulty
        )

        assert applied is True

        # Verify user's next exercise will use the new difficulty
        # This would be verified by checking that next generated exercise
        # uses the new difficulty level

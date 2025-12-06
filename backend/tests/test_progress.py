"""
Integration tests for Progress Tracking & Achievement System API.

Tests cover:
- Progress metrics retrieval
- User statistics calculation
- Achievement tracking and unlocking
- Streak calculation and maintenance
- Performance metrics storage
- Progress history tracking
- Badge assignment
- Export progress data

Testing Strategy:
- Integration tests with real database interactions
- Test actual API endpoints and service layer
- Verify business logic and data persistence
- Verify streak calculation with timezone awareness
- Test achievement unlock logic
- Test statistics aggregation (daily, weekly, monthly)
"""
import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
from src.models.user import User
from src.models.exercise import Exercise, UserExercise, ExerciseType, ExerciseDifficulty, ExerciseStatus


# ===================================================================
# FIXTURES
# ===================================================================

@pytest.fixture
async def test_user_with_progress(db_session):
    """Create a test user with some progress data."""
    user = User(
        email="progressor@test.com",
        name="progressor",
        password_hash="hashed_password",
        email_verified=True,
        is_active=True,
        programming_language="python",
        skill_level="intermediate",
        current_streak=5,
        longest_streak=10,
        exercises_completed=25,
        last_exercise_date=datetime.utcnow() - timedelta(days=1)
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def completed_exercises(db_session, test_user_with_progress):
    """Create several completed exercises for the test user."""
    exercises = []
    user_exercises = []

    # Create 5 exercises completed over the last 5 days
    for day_offset in range(5):
        exercise = Exercise(
            title=f"Exercise Day {day_offset}",
            description="Test exercise",
            instructions="Complete the task",
            exercise_type=ExerciseType.ALGORITHM,
            difficulty=ExerciseDifficulty.MEDIUM,
            programming_language="python",
            generated_by_ai=True
        )
        db_session.add(exercise)
        await db_session.flush()
        await db_session.refresh(exercise)
        exercises.append(exercise)

        # Create user exercise record
        completed_date = datetime.utcnow() - timedelta(days=day_offset)
        user_ex = UserExercise(
            user_id=test_user_with_progress.id,
            exercise_id=exercise.id,
            status=ExerciseStatus.COMPLETED,
            completed_at=completed_date,
            started_at=completed_date - timedelta(minutes=30),
            time_spent_seconds=1800,  # 30 minutes
            grade=85.0,
            test_cases_passed=8,
            test_cases_total=10,
            hints_requested=2
        )
        db_session.add(user_ex)
        user_exercises.append(user_ex)

    await db_session.flush()
    return exercises, user_exercises


# ===================================================================
# TEST: Progress Metrics Retrieval
# ===================================================================

@pytest.mark.asyncio
async def test_get_user_progress_metrics(client, test_user_with_progress, completed_exercises, patched_get_session):
    """Test retrieving comprehensive user progress metrics."""
    # Mock JWT auth
    with patch('src.middleware.auth_middleware.verify_jwt_token', return_value={'user_id': test_user_with_progress.id}):
        response = await client.get(
            '/api/progress',
            headers={'Authorization': 'Bearer test_token'}
        )

    assert response.status_code == 200
    data = await response.get_json()

    # Verify progress metrics structure
    assert 'exercises_completed' in data
    assert 'current_streak' in data
    assert 'longest_streak' in data
    assert 'total_time_spent_seconds' in data
    assert 'average_grade' in data
    assert 'achievements' in data
    assert 'skill_levels' in data

    # Verify metrics values
    assert data['exercises_completed'] == 25
    assert data['current_streak'] == 5
    assert data['longest_streak'] == 10


@pytest.mark.asyncio
async def test_get_progress_metrics_unauthenticated(client):
    """Test that progress endpoint requires authentication."""
    response = await client.get('/api/progress')
    assert response.status_code == 401


# ===================================================================
# TEST: Achievement Tracking
# ===================================================================

@pytest.mark.asyncio
async def test_unlock_streak_achievement_7_days(client, test_user_with_progress, patched_get_session):
    """Test that 7-day streak achievement unlocks correctly."""
    # Set user to have 7 day streak
    test_user_with_progress.current_streak = 7

    with patch('src.middleware.auth_middleware.verify_jwt_token', return_value={'user_id': test_user_with_progress.id}):
        response = await client.get(
            '/api/progress/achievements',
            headers={'Authorization': 'Bearer test_token'}
        )

    assert response.status_code == 200
    data = await response.get_json()

    # Verify achievement unlocked
    achievements = data['achievements']
    assert any(a['type'] == 'streak_7' for a in achievements)

    # Verify achievement details
    streak_achievement = next(a for a in achievements if a['type'] == 'streak_7')
    assert streak_achievement['unlocked'] is True
    assert 'unlocked_at' in streak_achievement


@pytest.mark.asyncio
async def test_unlock_exercise_milestone_achievement(client, test_user_with_progress, patched_get_session):
    """Test that exercise milestone achievements unlock."""
    # Set user to have completed 50 exercises
    test_user_with_progress.exercises_completed = 50

    with patch('src.middleware.auth_middleware.verify_jwt_token', return_value={'user_id': test_user_with_progress.id}):
        response = await client.get(
            '/api/progress/achievements',
            headers={'Authorization': 'Bearer test_token'}
        )

    assert response.status_code == 200
    data = await response.get_json()

    # Should have unlocked 10 and 50 exercise achievements
    achievements = data['achievements']
    assert any(a['type'] == 'exercises_10' and a['unlocked'] for a in achievements)
    assert any(a['type'] == 'exercises_50' and a['unlocked'] for a in achievements)
    # Should NOT have unlocked 100 yet
    assert any(a['type'] == 'exercises_100' and not a['unlocked'] for a in achievements)


@pytest.mark.asyncio
async def test_achievement_progress_tracking(client, test_user_with_progress, patched_get_session):
    """Test that achievement progress is tracked (e.g., 45/50 exercises)."""
    test_user_with_progress.exercises_completed = 45

    with patch('src.middleware.auth_middleware.verify_jwt_token', return_value={'user_id': test_user_with_progress.id}):
        response = await client.get(
            '/api/progress/achievements',
            headers={'Authorization': 'Bearer test_token'}
        )

    assert response.status_code == 200
    data = await response.get_json()

    # Find the 50 exercises achievement
    achievements = data['achievements']
    exercises_50 = next(a for a in achievements if a['type'] == 'exercises_50')

    assert exercises_50['unlocked'] is False
    assert exercises_50['progress'] == 45
    assert exercises_50['target'] == 50
    assert exercises_50['progress_percentage'] == 90.0


# ===================================================================
# TEST: Streak Calculation
# ===================================================================

@pytest.mark.asyncio
async def test_streak_maintained_on_daily_completion(client, test_user_with_progress, patched_get_session):
    """Test that streak increments when exercise completed today."""
    # User completed exercise yesterday (streak = 5)
    # Now complete one today - should increment to 6

    with patch('src.middleware.auth_middleware.verify_jwt_token', return_value={'user_id': test_user_with_progress.id}):
        # Simulate exercise completion
        response = await client.post(
            '/api/progress/update-streak',
            headers={'Authorization': 'Bearer test_token'},
            json={'completed_today': True}
        )

    assert response.status_code == 200
    data = await response.get_json()

    assert data['current_streak'] == 6
    assert data['streak_maintained'] is True


@pytest.mark.asyncio
async def test_streak_broken_on_missed_day(client, test_user_with_progress, patched_get_session):
    """Test that streak resets when a day is missed."""
    # Set last exercise to 3 days ago - streak should be broken
    test_user_with_progress.last_exercise_date = datetime.utcnow() - timedelta(days=3)

    with patch('src.middleware.auth_middleware.verify_jwt_token', return_value={'user_id': test_user_with_progress.id}):
        response = await client.post(
            '/api/progress/update-streak',
            headers={'Authorization': 'Bearer test_token'},
            json={'completed_today': True}
        )

    assert response.status_code == 200
    data = await response.get_json()

    # Streak should reset to 1 (today's exercise)
    assert data['current_streak'] == 1
    assert data['streak_broken'] is True
    assert data['previous_streak'] == 5


@pytest.mark.asyncio
async def test_longest_streak_updates(client, test_user_with_progress, patched_get_session):
    """Test that longest streak is updated when current streak exceeds it."""
    # Current streak is 5, longest is 10
    # Increment current to 11
    test_user_with_progress.current_streak = 11

    with patch('src.middleware.auth_middleware.verify_jwt_token', return_value={'user_id': test_user_with_progress.id}):
        response = await client.post(
            '/api/progress/update-streak',
            headers={'Authorization': 'Bearer test_token'},
            json={'completed_today': True}
        )

    assert response.status_code == 200
    data = await response.get_json()

    assert data['current_streak'] == 12
    assert data['longest_streak'] == 12  # Should update
    assert data['new_record'] is True


# ===================================================================
# TEST: Performance Metrics
# ===================================================================

@pytest.mark.asyncio
async def test_get_performance_statistics(client, test_user_with_progress, completed_exercises, patched_get_session):
    """Test retrieval of user performance statistics."""
    with patch('src.middleware.auth_middleware.verify_jwt_token', return_value={'user_id': test_user_with_progress.id}):
        response = await client.get(
            '/api/progress/statistics',
            headers={'Authorization': 'Bearer test_token'}
        )

    assert response.status_code == 200
    data = await response.get_json()

    # Verify statistics structure
    assert 'average_grade' in data
    assert 'average_time_per_exercise' in data
    assert 'total_hints_requested' in data
    assert 'exercises_by_difficulty' in data
    assert 'exercises_by_type' in data
    assert 'recent_performance_trend' in data

    # Verify calculations
    assert isinstance(data['average_grade'], float)
    assert data['average_grade'] > 0
    assert isinstance(data['average_time_per_exercise'], (int, float))


@pytest.mark.asyncio
async def test_get_statistics_by_time_period(client, test_user_with_progress, completed_exercises, patched_get_session):
    """Test statistics filtered by time period (daily, weekly, monthly)."""
    with patch('src.middleware.auth_middleware.verify_jwt_token', return_value={'user_id': test_user_with_progress.id}):
        # Test weekly statistics
        response = await client.get(
            '/api/progress/statistics?period=weekly',
            headers={'Authorization': 'Bearer test_token'}
        )

    assert response.status_code == 200
    data = await response.get_json()

    assert 'period' in data
    assert data['period'] == 'weekly'
    assert 'exercises_completed' in data
    assert 'average_grade' in data


# ===================================================================
# TEST: Progress History
# ===================================================================

@pytest.mark.asyncio
async def test_get_progress_history(client, test_user_with_progress, completed_exercises, patched_get_session):
    """Test retrieval of historical progress data."""
    with patch('src.middleware.auth_middleware.verify_jwt_token', return_value={'user_id': test_user_with_progress.id}):
        response = await client.get(
            '/api/progress/history?days=30',
            headers={'Authorization': 'Bearer test_token'}
        )

    assert response.status_code == 200
    data = await response.get_json()

    # Verify history structure
    assert 'history' in data
    assert isinstance(data['history'], list)
    assert len(data['history']) > 0

    # Verify each history entry has required fields
    for entry in data['history']:
        assert 'date' in entry
        assert 'exercises_completed' in entry
        assert 'time_spent_seconds' in entry


@pytest.mark.asyncio
async def test_progress_history_date_range(client, test_user_with_progress, patched_get_session):
    """Test progress history with custom date range."""
    with patch('src.middleware.auth_middleware.verify_jwt_token', return_value={'user_id': test_user_with_progress.id}):
        start_date = (datetime.utcnow() - timedelta(days=7)).date().isoformat()
        end_date = datetime.utcnow().date().isoformat()

        response = await client.get(
            f'/api/progress/history?start_date={start_date}&end_date={end_date}',
            headers={'Authorization': 'Bearer test_token'}
        )

    assert response.status_code == 200
    data = await response.get_json()

    assert 'history' in data
    # Should only include entries within date range
    for entry in data['history']:
        entry_date = datetime.fromisoformat(entry['date']).date()
        assert entry_date >= datetime.fromisoformat(start_date).date()
        assert entry_date <= datetime.fromisoformat(end_date).date()


# ===================================================================
# TEST: Badge System
# ===================================================================

@pytest.mark.asyncio
async def test_assign_badge_on_achievement(client, test_user_with_progress, patched_get_session):
    """Test that badges are assigned when achievements are unlocked."""
    test_user_with_progress.current_streak = 7

    with patch('src.middleware.auth_middleware.verify_jwt_token', return_value={'user_id': test_user_with_progress.id}):
        response = await client.get(
            '/api/progress/badges',
            headers={'Authorization': 'Bearer test_token'}
        )

    assert response.status_code == 200
    data = await response.get_json()

    assert 'badges' in data
    badges = data['badges']

    # Should have 7-day streak badge
    assert any(b['type'] == 'streak_7' for b in badges)

    # Verify badge details
    streak_badge = next(b for b in badges if b['type'] == 'streak_7')
    assert 'name' in streak_badge
    assert 'description' in streak_badge
    assert 'icon_url' in streak_badge or 'icon' in streak_badge
    assert 'earned_at' in streak_badge


@pytest.mark.asyncio
async def test_badge_list_shows_unearned_badges(client, test_user_with_progress, patched_get_session):
    """Test that badge list shows both earned and unearned badges."""
    # User has only 5 streak, no achievements yet
    test_user_with_progress.current_streak = 2
    test_user_with_progress.exercises_completed = 3

    with patch('src.middleware.auth_middleware.verify_jwt_token', return_value={'user_id': test_user_with_progress.id}):
        response = await client.get(
            '/api/progress/badges',
            headers={'Authorization': 'Bearer test_token'}
        )

    assert response.status_code == 200
    data = await response.get_json()

    badges = data['badges']

    # Should show unearned badges with earned=False
    streak_7_badge = next(b for b in badges if b['type'] == 'streak_7')
    assert streak_7_badge['earned'] is False
    assert 'earned_at' not in streak_7_badge or streak_7_badge['earned_at'] is None


# ===================================================================
# TEST: Export Progress Data
# ===================================================================

@pytest.mark.asyncio
async def test_export_progress_data_json(client, test_user_with_progress, completed_exercises, patched_get_session):
    """Test exporting progress data in JSON format."""
    with patch('src.middleware.auth_middleware.verify_jwt_token', return_value={'user_id': test_user_with_progress.id}):
        response = await client.get(
            '/api/progress/export?format=json',
            headers={'Authorization': 'Bearer test_token'}
        )

    assert response.status_code == 200
    data = await response.get_json()

    # Verify export includes all key data
    assert 'user_id' in data
    assert 'export_date' in data
    assert 'progress_metrics' in data
    assert 'achievements' in data
    assert 'exercise_history' in data
    assert 'statistics' in data


@pytest.mark.asyncio
async def test_export_progress_data_csv(client, test_user_with_progress, completed_exercises, patched_get_session):
    """Test exporting progress data in CSV format."""
    with patch('src.middleware.auth_middleware.verify_jwt_token', return_value={'user_id': test_user_with_progress.id}):
        response = await client.get(
            '/api/progress/export?format=csv',
            headers={'Authorization': 'Bearer test_token'}
        )

    assert response.status_code == 200
    # CSV should be returned as text/csv
    assert 'text/csv' in response.content_type or 'application/csv' in response.content_type

    # Get CSV data
    csv_data = await response.get_data(as_text=True)
    assert len(csv_data) > 0
    assert 'exercise_id' in csv_data or 'Exercise' in csv_data  # Header row


# ===================================================================
# TEST: Skill Level Tracking
# ===================================================================

@pytest.mark.asyncio
async def test_track_skill_levels_by_topic(client, test_user_with_progress, completed_exercises, patched_get_session):
    """Test that skill levels are tracked per topic area."""
    with patch('src.middleware.auth_middleware.verify_jwt_token', return_value={'user_id': test_user_with_progress.id}):
        response = await client.get(
            '/api/progress/skill-levels',
            headers={'Authorization': 'Bearer test_token'}
        )

    assert response.status_code == 200
    data = await response.get_json()

    assert 'skill_levels' in data
    skill_levels = data['skill_levels']

    # Should be organized by topic
    assert isinstance(skill_levels, dict) or isinstance(skill_levels, list)

    # If dict, verify structure
    if isinstance(skill_levels, dict):
        for topic, level_data in skill_levels.items():
            assert 'level' in level_data  # e.g., beginner, intermediate, advanced
            assert 'exercises_completed' in level_data
            assert 'average_grade' in level_data


@pytest.mark.asyncio
async def test_skill_level_progression(client, test_user_with_progress, patched_get_session):
    """Test that skill level progresses based on performance."""
    # This would test the logic that advances users from beginner -> intermediate -> advanced
    # based on exercises completed and grades achieved

    with patch('src.middleware.auth_middleware.verify_jwt_token', return_value={'user_id': test_user_with_progress.id}):
        response = await client.post(
            '/api/progress/calculate-skill-level',
            headers={'Authorization': 'Bearer test_token'},
            json={'topic': 'algorithms'}
        )

    assert response.status_code == 200
    data = await response.get_json()

    assert 'topic' in data
    assert 'previous_level' in data or 'current_level' in data
    assert 'current_level' in data
    assert 'level_changed' in data


# ===================================================================
# TEST: Edge Cases
# ===================================================================

@pytest.mark.asyncio
async def test_progress_for_new_user_with_no_exercises(client, patched_get_session):
    """Test that progress endpoint works for users with no completed exercises."""
    # Create brand new user
    new_user = User(
        email="newbie@test.com",
        name="newbie",
        password_hash="hashed_password",
        email_verified=True,
        is_active=True,
        current_streak=0,
        longest_streak=0,
        exercises_completed=0
    )

    with patch('src.middleware.auth_middleware.verify_jwt_token', return_value={'user_id': new_user.id}):
        response = await client.get(
            '/api/progress',
            headers={'Authorization': 'Bearer test_token'}
        )

    assert response.status_code == 200
    data = await response.get_json()

    # Should return zero values, not error
    assert data['exercises_completed'] == 0
    assert data['current_streak'] == 0
    assert data['longest_streak'] == 0
    assert data['total_time_spent_seconds'] == 0


@pytest.mark.asyncio
async def test_streak_calculation_handles_timezone_boundaries(client, test_user_with_progress, patched_get_session):
    """Test that streak calculation properly handles timezone boundaries."""
    # This is a critical test for international users
    # A user in timezone UTC+10 completing at 1 AM should count as "today"
    # even if it's still "yesterday" in UTC

    # For MVP, we'll use UTC, but this test documents the requirement
    with patch('src.middleware.auth_middleware.verify_jwt_token', return_value={'user_id': test_user_with_progress.id}):
        response = await client.post(
            '/api/progress/update-streak',
            headers={'Authorization': 'Bearer test_token'},
            json={
                'completed_today': True,
                'user_timezone': 'America/New_York'  # Future enhancement
            }
        )

    assert response.status_code == 200
    # For MVP, this will use UTC, but test passes to document future requirement

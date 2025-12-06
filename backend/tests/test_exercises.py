"""
Integration tests for Exercise Generation & Management API.

Tests cover:
- Daily exercise generation (personalized)
- Exercise retrieval
- Exercise submission
- Hint requests
- Exercise history
- Exercise completion tracking
- Multi-language support
- Difficulty personalization

Testing Strategy:
- Integration tests with real database interactions
- Mock only external LLM API calls
- Test actual API endpoints and service layer
- Verify business logic and data persistence
"""
import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
from src.models.user import User
from src.models.exercise import Exercise, UserExercise, ExerciseType, ExerciseDifficulty, ExerciseStatus
from src.models.user_memory import UserMemory


# ===================================================================
# FIXTURES
# ===================================================================

@pytest.fixture
async def test_user(db_session):
    """Create a test user with profile data."""
    user = User(
        email="exerciser@test.com",
        username="exerciser",
        password_hash="hashed_password",
        email_verified=True,
        is_active=True,
        primary_language="python",
        skill_level="intermediate",
        learning_goals="Master algorithms and data structures",
        preferred_topics="algorithms,data_structures,problem_solving"
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_exercise(db_session):
    """Create a test exercise."""
    exercise = Exercise(
        title="Two Sum Problem",
        description="Find two numbers in an array that add up to a target sum.",
        instructions="Given an array of integers and a target sum, return indices of two numbers that add up to the target.",
        starter_code="def two_sum(nums, target):\n    pass",
        solution="def two_sum(nums, target):\n    seen = {}\n    for i, num in enumerate(nums):\n        complement = target - num\n        if complement in seen:\n            return [seen[complement], i]\n        seen[num] = i",
        exercise_type=ExerciseType.ALGORITHM,
        difficulty=ExerciseDifficulty.MEDIUM,
        programming_language="python",
        topics="arrays,hash_tables",
        test_cases='[{"input": {"nums": [2,7,11,15], "target": 9}, "output": [0,1]}]',
        generated_by_ai=True
    )
    db_session.add(exercise)
    await db_session.flush()
    await db_session.refresh(exercise)
    return exercise


@pytest.fixture
async def user_exercise(db_session, test_user, test_exercise):
    """Create a user exercise record."""
    user_ex = UserExercise(
        user_id=test_user.id,
        exercise_id=test_exercise.id,
        status=ExerciseStatus.IN_PROGRESS,
        started_at=datetime.utcnow()
    )
    db_session.add(user_ex)
    await db_session.flush()
    await db_session.refresh(user_ex)
    return user_ex


@pytest.fixture
def mock_llm_service():
    """Mock LLM service for exercise generation."""
    with patch('src.services.exercise_service.LLMService') as mock_service_class:
        mock_service = AsyncMock()
        mock_service_class.return_value = mock_service

        # Mock exercise generation response
        mock_service.generate_exercise = AsyncMock(return_value={
            "title": "Reverse a Linked List",
            "description": "Implement a function to reverse a singly linked list",
            "instructions": "Given the head of a singly linked list, reverse the list and return the new head.",
            "starter_code": "class ListNode:\n    def __init__(self, val=0, next=None):\n        self.val = val\n        self.next = next\n\ndef reverse_list(head: ListNode) -> ListNode:\n    pass",
            "solution": "def reverse_list(head):\n    prev = None\n    while head:\n        next_node = head.next\n        head.next = prev\n        prev = head\n        head = next_node\n    return prev",
            "test_cases": [
                {"input": {"head": [1,2,3,4,5]}, "output": [5,4,3,2,1]}
            ],
            "topics": ["linked_lists", "pointers"],
            "difficulty": "medium"
        })

        # Mock hint generation
        mock_service.generate_hint = AsyncMock(return_value={
            "hint": "Consider using three pointers: previous, current, and next. Update the pointers as you traverse the list."
        })

        # Mock submission feedback
        mock_service.evaluate_submission = AsyncMock(return_value={
            "grade": 85.0,
            "feedback": "Good solution! Your implementation correctly reverses the linked list. Consider edge cases like empty lists.",
            "strengths": ["Correct algorithm", "Good variable naming"],
            "improvements": ["Add edge case handling", "Consider iterative vs recursive approaches"]
        })

        yield mock_service


# ===================================================================
# TEST: Daily Exercise Generation
# ===================================================================

@pytest.mark.asyncio
async def test_generate_daily_exercise_new_user(client, test_user, patched_get_session, mock_llm_service):
    """Test generating daily exercise for user who hasn't received one today."""
    # Mock JWT auth
    with patch('src.middleware.auth.verify_jwt_token', return_value={'user_id': test_user.id}):
        response = await client.get(
            '/api/exercises/daily',
            headers={'Authorization': 'Bearer test_token'}
        )

    assert response.status_code == 200
    data = await response.get_json()

    # Verify response structure
    assert 'exercise' in data
    assert data['exercise']['title'] == "Reverse a Linked List"
    assert data['exercise']['programming_language'] == test_user.primary_language
    assert 'user_exercise_id' in data  # Should track user's progress

    # Verify LLM was called with user context
    mock_llm_service.generate_exercise.assert_called_once()
    call_args = mock_llm_service.generate_exercise.call_args
    assert test_user.primary_language in str(call_args)
    assert test_user.skill_level in str(call_args)


@pytest.mark.asyncio
async def test_get_daily_exercise_already_exists(client, test_user, test_exercise, user_exercise, patched_get_session):
    """Test retrieving existing daily exercise (don't generate new one)."""
    with patch('src.middleware.auth.verify_jwt_token', return_value={'user_id': test_user.id}):
        response = await client.get(
            '/api/exercises/daily',
            headers={'Authorization': 'Bearer test_token'}
        )

    assert response.status_code == 200
    data = await response.get_json()

    # Should return existing exercise
    assert data['exercise']['id'] == test_exercise.id
    assert data['exercise']['title'] == test_exercise.title
    assert data['user_exercise_id'] == user_exercise.id
    assert data['status'] == ExerciseStatus.IN_PROGRESS.value


@pytest.mark.asyncio
async def test_daily_exercise_unauthorized(client):
    """Test daily exercise endpoint requires authentication."""
    response = await client.get('/api/exercises/daily')
    assert response.status_code == 401


# ===================================================================
# TEST: Exercise Retrieval
# ===================================================================

@pytest.mark.asyncio
async def test_get_exercise_by_id(client, test_user, test_exercise, patched_get_session):
    """Test retrieving specific exercise by ID."""
    with patch('src.middleware.auth.verify_jwt_token', return_value={'user_id': test_user.id}):
        response = await client.get(
            f'/api/exercises/{test_exercise.id}',
            headers={'Authorization': 'Bearer test_token'}
        )

    assert response.status_code == 200
    data = await response.get_json()

    assert data['id'] == test_exercise.id
    assert data['title'] == test_exercise.title
    assert data['description'] == test_exercise.description
    assert data['instructions'] == test_exercise.instructions
    assert data['starter_code'] == test_exercise.starter_code
    assert 'solution' not in data  # Solution should not be returned


@pytest.mark.asyncio
async def test_get_exercise_not_found(client, test_user, patched_get_session):
    """Test retrieving non-existent exercise returns 404."""
    with patch('src.middleware.auth.verify_jwt_token', return_value={'user_id': test_user.id}):
        response = await client.get(
            '/api/exercises/99999',
            headers={'Authorization': 'Bearer test_token'}
        )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_exercise_list(client, test_user, test_exercise, patched_get_session):
    """Test listing user's exercises with pagination."""
    with patch('src.middleware.auth.verify_jwt_token', return_value={'user_id': test_user.id}):
        response = await client.get(
            '/api/exercises?limit=10&offset=0',
            headers={'Authorization': 'Bearer test_token'}
        )

    assert response.status_code == 200
    data = await response.get_json()

    assert 'exercises' in data
    assert 'total' in data
    assert 'limit' in data
    assert 'offset' in data
    assert isinstance(data['exercises'], list)


# ===================================================================
# TEST: Exercise Submission
# ===================================================================

@pytest.mark.asyncio
async def test_submit_exercise_solution(client, test_user, test_exercise, user_exercise, patched_get_session, mock_llm_service):
    """Test submitting a solution for an exercise."""
    solution_code = """
def two_sum(nums, target):
    seen = {}
    for i, num in enumerate(nums):
        complement = target - num
        if complement in seen:
            return [seen[complement], i]
        seen[num] = i
    return []
"""

    with patch('src.middleware.auth.verify_jwt_token', return_value={'user_id': test_user.id}):
        response = await client.post(
            f'/api/exercises/{test_exercise.id}/submit',
            headers={'Authorization': 'Bearer test_token'},
            json={'solution': solution_code}
        )

    assert response.status_code == 200
    data = await response.get_json()

    # Verify feedback structure
    assert 'grade' in data
    assert 'feedback' in data
    assert 'strengths' in data
    assert 'improvements' in data

    # Verify LLM evaluation was called
    mock_llm_service.evaluate_submission.assert_called_once()


@pytest.mark.asyncio
async def test_submit_exercise_validation(client, test_user, test_exercise, patched_get_session):
    """Test solution submission validation."""
    with patch('src.middleware.auth.verify_jwt_token', return_value={'user_id': test_user.id}):
        # Empty solution
        response = await client.post(
            f'/api/exercises/{test_exercise.id}/submit',
            headers={'Authorization': 'Bearer test_token'},
            json={'solution': ''}
        )
        assert response.status_code == 400

        # Missing solution field
        response = await client.post(
            f'/api/exercises/{test_exercise.id}/submit',
            headers={'Authorization': 'Bearer test_token'},
            json={}
        )
        assert response.status_code == 400


@pytest.mark.asyncio
async def test_submit_exercise_not_found(client, test_user, patched_get_session):
    """Test submitting solution for non-existent exercise."""
    with patch('src.middleware.auth.verify_jwt_token', return_value={'user_id': test_user.id}):
        response = await client.post(
            '/api/exercises/99999/submit',
            headers={'Authorization': 'Bearer test_token'},
            json={'solution': 'code here'}
        )

    assert response.status_code == 404


# ===================================================================
# TEST: Hint Requests
# ===================================================================

@pytest.mark.asyncio
async def test_request_hint(client, test_user, test_exercise, user_exercise, patched_get_session, mock_llm_service):
    """Test requesting a hint for an exercise."""
    with patch('src.middleware.auth.verify_jwt_token', return_value={'user_id': test_user.id}):
        response = await client.post(
            f'/api/exercises/{test_exercise.id}/hint',
            headers={'Authorization': 'Bearer test_token'}
        )

    assert response.status_code == 200
    data = await response.get_json()

    # Verify hint structure
    assert 'hint' in data
    assert 'hints_used' in data
    assert len(data['hint']) > 0

    # Verify hint doesn't reveal full solution
    assert 'solution' not in data

    # Verify LLM was called
    mock_llm_service.generate_hint.assert_called_once()


@pytest.mark.asyncio
async def test_hint_increments_counter(client, test_user, test_exercise, user_exercise, patched_get_session, mock_llm_service):
    """Test that requesting hints increments the hints_requested counter."""
    initial_hints = user_exercise.hints_requested

    with patch('src.middleware.auth.verify_jwt_token', return_value={'user_id': test_user.id}):
        response = await client.post(
            f'/api/exercises/{test_exercise.id}/hint',
            headers={'Authorization': 'Bearer test_token'}
        )

    assert response.status_code == 200
    data = await response.get_json()

    # Verify counter incremented
    assert data['hints_used'] == initial_hints + 1


# ===================================================================
# TEST: Exercise History
# ===================================================================

@pytest.mark.asyncio
async def test_get_exercise_history(client, test_user, test_exercise, user_exercise, patched_get_session):
    """Test retrieving user's exercise history."""
    with patch('src.middleware.auth.verify_jwt_token', return_value={'user_id': test_user.id}):
        response = await client.get(
            '/api/exercises/history',
            headers={'Authorization': 'Bearer test_token'}
        )

    assert response.status_code == 200
    data = await response.get_json()

    assert 'exercises' in data
    assert 'total' in data
    assert len(data['exercises']) > 0

    # Verify exercise details
    first_ex = data['exercises'][0]
    assert 'exercise_id' in first_ex
    assert 'title' in first_ex
    assert 'status' in first_ex
    assert 'started_at' in first_ex


@pytest.mark.asyncio
async def test_exercise_history_filtering(client, test_user, patched_get_session):
    """Test filtering exercise history by status."""
    with patch('src.middleware.auth.verify_jwt_token', return_value={'user_id': test_user.id}):
        # Filter by completed
        response = await client.get(
            '/api/exercises/history?status=completed',
            headers={'Authorization': 'Bearer test_token'}
        )
        assert response.status_code == 200
        data = await response.get_json()
        assert 'exercises' in data


@pytest.mark.asyncio
async def test_exercise_history_pagination(client, test_user, patched_get_session):
    """Test pagination of exercise history."""
    with patch('src.middleware.auth.verify_jwt_token', return_value={'user_id': test_user.id}):
        response = await client.get(
            '/api/exercises/history?limit=5&offset=0',
            headers={'Authorization': 'Bearer test_token'}
        )
        assert response.status_code == 200
        data = await response.get_json()

        assert data['limit'] == 5
        assert data['offset'] == 0


# ===================================================================
# TEST: Exercise Completion
# ===================================================================

@pytest.mark.asyncio
async def test_mark_exercise_complete(client, test_user, test_exercise, user_exercise, patched_get_session):
    """Test marking an exercise as complete."""
    with patch('src.middleware.auth.verify_jwt_token', return_value={'user_id': test_user.id}):
        response = await client.post(
            f'/api/exercises/{test_exercise.id}/complete',
            headers={'Authorization': 'Bearer test_token'}
        )

    assert response.status_code == 200
    data = await response.get_json()

    assert data['status'] == ExerciseStatus.COMPLETED.value
    assert 'completed_at' in data
    assert data['completed_at'] is not None


# ===================================================================
# TEST: Multi-Language Support
# ===================================================================

@pytest.mark.asyncio
async def test_exercise_generation_javascript(client, test_user, patched_get_session, mock_llm_service):
    """Test generating exercise for JavaScript language."""
    # Update user's primary language
    test_user.primary_language = "javascript"

    with patch('src.middleware.auth.verify_jwt_token', return_value={'user_id': test_user.id}):
        response = await client.get(
            '/api/exercises/daily',
            headers={'Authorization': 'Bearer test_token'}
        )

    assert response.status_code == 200

    # Verify LLM was called with JavaScript context
    mock_llm_service.generate_exercise.assert_called()
    call_args = str(mock_llm_service.generate_exercise.call_args)
    assert 'javascript' in call_args.lower()


# ===================================================================
# TEST: Personalization
# ===================================================================

@pytest.mark.asyncio
async def test_exercise_personalized_to_skill_level(client, test_user, patched_get_session, mock_llm_service):
    """Test that exercises are personalized based on user skill level."""
    test_user.skill_level = "beginner"

    with patch('src.middleware.auth.verify_jwt_token', return_value={'user_id': test_user.id}):
        response = await client.get(
            '/api/exercises/daily',
            headers={'Authorization': 'Bearer test_token'}
        )

    assert response.status_code == 200

    # Verify LLM was called with skill level
    mock_llm_service.generate_exercise.assert_called()
    call_args = str(mock_llm_service.generate_exercise.call_args)
    assert 'beginner' in call_args.lower()


@pytest.mark.asyncio
async def test_exercise_personalized_to_interests(client, test_user, patched_get_session, mock_llm_service):
    """Test that exercises consider user's learning goals and interests."""
    test_user.learning_goals = "Web development with React"
    test_user.preferred_topics = "frontend,javascript,react"

    with patch('src.middleware.auth.verify_jwt_token', return_value={'user_id': test_user.id}):
        response = await client.get(
            '/api/exercises/daily',
            headers={'Authorization': 'Bearer test_token'}
        )

    assert response.status_code == 200

    # Verify LLM context included user interests
    mock_llm_service.generate_exercise.assert_called()

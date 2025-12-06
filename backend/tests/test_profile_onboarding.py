"""
Integration tests for profile and onboarding API endpoints.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.models.user import User, SkillLevel, UserRole
from src.services.profile_service import ProfileService
from datetime import datetime


@pytest.fixture
def mock_user():
    """Create a mock user for testing."""
    user = MagicMock(spec=User)
    user.id = 1
    user.email = "test@example.com"
    user.name = "Test User"
    user.password_hash = "hashed_password"
    user.email_verified = True
    user.role = UserRole.STUDENT
    user.is_active = True
    user.is_mentor = False
    user.programming_language = None
    user.skill_level = None
    user.career_goals = None
    user.learning_style = None
    user.time_commitment = None
    user.onboarding_completed = False
    user.current_streak = 0
    user.longest_streak = 0
    user.exercises_completed = 0
    user.last_exercise_date = None
    user.avatar_url = None
    user.bio = None
    user.github_id = None
    user.google_id = None
    user.oauth_provider = None
    user.created_at = datetime.now()
    user.updated_at = datetime.now()
    user.last_login = None
    return user


@pytest.fixture
def onboarded_user(mock_user):
    """Create a mock user who has completed onboarding."""
    mock_user.programming_language = "python"
    mock_user.skill_level = SkillLevel.INTERMEDIATE
    mock_user.career_goals = "Become a full-stack developer"
    mock_user.learning_style = "hands-on"
    mock_user.time_commitment = "1-2 hours/day"
    mock_user.onboarding_completed = True
    return mock_user


class TestOnboardingQuestions:
    """Tests for onboarding questions endpoint."""

    @pytest.mark.asyncio
    async def test_get_onboarding_questions_success(self, client):
        """Test successful retrieval of onboarding questions."""
        # Mock authentication
        with patch('src.middleware.auth_middleware.AuthService.verify_jwt_token') as mock_verify, \
             patch('src.middleware.auth_middleware.AuthService.validate_session') as mock_validate:

            mock_verify.return_value = {
                "user_id": 1,
                "email": "test@example.com",
                "role": "student",
                "jti": "test-jti"
            }
            mock_validate.return_value = True

            response = await client.get(
                "/api/users/onboarding/questions",
                headers={"Authorization": "Bearer test-token"}
            )

            assert response.status_code == 200
            data = await response.get_json()
            assert "questions" in data
            assert "total_questions" in data
            assert "estimated_time" in data
            assert data["total_questions"] == 5
            assert len(data["questions"]) == 5

    @pytest.mark.asyncio
    async def test_get_onboarding_questions_unauthorized(self, client):
        """Test onboarding questions without authentication."""
        response = await client.get("/api/users/onboarding/questions")
        assert response.status_code == 401


class TestOnboardingStatus:
    """Tests for onboarding status endpoint."""

    @pytest.mark.asyncio
    async def test_get_onboarding_status_not_completed(self, client, mock_user):
        """Test onboarding status for user who hasn't completed onboarding."""
        with patch('src.middleware.auth_middleware.AuthService.verify_jwt_token') as mock_verify, \
             patch('src.middleware.auth_middleware.AuthService.validate_session') as mock_validate, \
             patch('src.services.profile_service.ProfileService.check_onboarding_status') as mock_status:

            mock_verify.return_value = {
                "user_id": 1,
                "email": "test@example.com",
                "role": "student",
                "jti": "test-jti"
            }
            mock_validate.return_value = True
            mock_status.return_value = {
                "onboarding_completed": False,
                "can_resume": True,
                "profile_complete": False
            }

            response = await client.get(
                "/api/users/onboarding/status",
                headers={"Authorization": "Bearer test-token"}
            )

            assert response.status_code == 200
            data = await response.get_json()
            assert data["onboarding_completed"] is False
            assert data["can_resume"] is True

    @pytest.mark.asyncio
    async def test_get_onboarding_status_completed(self, client, onboarded_user):
        """Test onboarding status for user who has completed onboarding."""
        with patch('src.middleware.auth_middleware.AuthService.verify_jwt_token') as mock_verify, \
             patch('src.middleware.auth_middleware.AuthService.validate_session') as mock_validate, \
             patch('src.services.profile_service.ProfileService.check_onboarding_status') as mock_status:

            mock_verify.return_value = {
                "user_id": 1,
                "email": "test@example.com",
                "role": "student",
                "jti": "test-jti"
            }
            mock_validate.return_value = True
            mock_status.return_value = {
                "onboarding_completed": True,
                "can_resume": False,
                "profile_complete": True
            }

            response = await client.get(
                "/api/users/onboarding/status",
                headers={"Authorization": "Bearer test-token"}
            )

            assert response.status_code == 200
            data = await response.get_json()
            assert data["onboarding_completed"] is True


class TestCompleteOnboarding:
    """Tests for completing onboarding interview."""

    @pytest.mark.asyncio
    async def test_complete_onboarding_success(self, client, mock_user):
        """Test successful onboarding completion."""
        onboarding_data = {
            "programming_language": "python",
            "skill_level": "beginner",
            "career_goals": "Become a full-stack developer with expertise in React and Node.js",
            "learning_style": "hands-on",
            "time_commitment": "1-2 hours/day"
        }

        mock_user.programming_language = onboarding_data["programming_language"]
        mock_user.skill_level = SkillLevel.BEGINNER
        mock_user.career_goals = onboarding_data["career_goals"]
        mock_user.learning_style = onboarding_data["learning_style"]
        mock_user.time_commitment = onboarding_data["time_commitment"]
        mock_user.onboarding_completed = True

        with patch('src.middleware.auth_middleware.AuthService.verify_jwt_token') as mock_verify, \
             patch('src.middleware.auth_middleware.AuthService.validate_session') as mock_validate, \
             patch('src.utils.database.get_async_db_session') as mock_db:

            mock_verify.return_value = {
                "user_id": 1,
                "email": "test@example.com",
                "role": "student",
                "jti": "test-jti"
            }
            mock_validate.return_value = True

            # Mock database session and query
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_user
            mock_session.execute.return_value = mock_result
            mock_db.return_value.__aenter__.return_value = mock_session

            response = await client.post(
                "/api/users/onboarding",
                json=onboarding_data,
                headers={"Authorization": "Bearer test-token"}
            )

            assert response.status_code == 200
            data = await response.get_json()
            assert data["onboarding_completed"] is True
            assert data["programming_language"] == "python"
            assert data["skill_level"] == "beginner"
            assert "message" in data

    @pytest.mark.asyncio
    async def test_complete_onboarding_invalid_language(self, client):
        """Test onboarding with invalid programming language."""
        onboarding_data = {
            "programming_language": "cobol",  # Unsupported language
            "skill_level": "beginner",
            "career_goals": "Become a full-stack developer",
            "learning_style": "hands-on",
            "time_commitment": "1-2 hours/day"
        }

        with patch('src.middleware.auth_middleware.AuthService.verify_jwt_token') as mock_verify, \
             patch('src.middleware.auth_middleware.AuthService.validate_session') as mock_validate:

            mock_verify.return_value = {
                "user_id": 1,
                "email": "test@example.com",
                "role": "student",
                "jti": "test-jti"
            }
            mock_validate.return_value = True

            response = await client.post(
                "/api/users/onboarding",
                json=onboarding_data,
                headers={"Authorization": "Bearer test-token"}
            )

            assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_complete_onboarding_missing_fields(self, client):
        """Test onboarding with missing required fields."""
        onboarding_data = {
            "programming_language": "python",
            "skill_level": "beginner"
            # Missing: career_goals, learning_style, time_commitment
        }

        with patch('src.middleware.auth_middleware.AuthService.verify_jwt_token') as mock_verify, \
             patch('src.middleware.auth_middleware.AuthService.validate_session') as mock_validate:

            mock_verify.return_value = {
                "user_id": 1,
                "email": "test@example.com",
                "role": "student",
                "jti": "test-jti"
            }
            mock_validate.return_value = True

            response = await client.post(
                "/api/users/onboarding",
                json=onboarding_data,
                headers={"Authorization": "Bearer test-token"}
            )

            assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_complete_onboarding_short_career_goals(self, client):
        """Test onboarding with career goals that are too short."""
        onboarding_data = {
            "programming_language": "python",
            "skill_level": "beginner",
            "career_goals": "code",  # Too short
            "learning_style": "hands-on",
            "time_commitment": "1-2 hours/day"
        }

        with patch('src.middleware.auth_middleware.AuthService.verify_jwt_token') as mock_verify, \
             patch('src.middleware.auth_middleware.AuthService.validate_session') as mock_validate:

            mock_verify.return_value = {
                "user_id": 1,
                "email": "test@example.com",
                "role": "student",
                "jti": "test-jti"
            }
            mock_validate.return_value = True

            response = await client.post(
                "/api/users/onboarding",
                json=onboarding_data,
                headers={"Authorization": "Bearer test-token"}
            )

            assert response.status_code == 400


class TestUserProfile:
    """Tests for user profile endpoints."""

    @pytest.mark.asyncio
    async def test_get_user_profile_success(self, client, onboarded_user):
        """Test successful retrieval of user profile."""
        with patch('src.middleware.auth_middleware.AuthService.verify_jwt_token') as mock_verify, \
             patch('src.middleware.auth_middleware.AuthService.validate_session') as mock_validate, \
             patch('src.utils.database.get_async_db_session') as mock_db:

            mock_verify.return_value = {
                "user_id": 1,
                "email": "test@example.com",
                "role": "student",
                "jti": "test-jti"
            }
            mock_validate.return_value = True

            # Mock database session
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = onboarded_user
            mock_session.execute.return_value = mock_result
            mock_db.return_value.__aenter__.return_value = mock_session

            response = await client.get(
                "/api/users/me",
                headers={"Authorization": "Bearer test-token"}
            )

            assert response.status_code == 200
            data = await response.get_json()
            assert data["id"] == 1
            assert data["email"] == "test@example.com"
            assert data["programming_language"] == "python"

    @pytest.mark.asyncio
    async def test_update_user_profile_success(self, client, onboarded_user):
        """Test successful profile update."""
        update_data = {
            "name": "Updated Name",
            "skill_level": "advanced"
        }

        onboarded_user.name = "Updated Name"
        onboarded_user.skill_level = SkillLevel.ADVANCED

        with patch('src.middleware.auth_middleware.AuthService.verify_jwt_token') as mock_verify, \
             patch('src.middleware.auth_middleware.AuthService.validate_session') as mock_validate, \
             patch('src.utils.database.get_async_db_session') as mock_db:

            mock_verify.return_value = {
                "user_id": 1,
                "email": "test@example.com",
                "role": "student",
                "jti": "test-jti"
            }
            mock_validate.return_value = True

            # Mock database session
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = onboarded_user
            mock_session.execute.return_value = mock_result
            mock_db.return_value.__aenter__.return_value = mock_session

            response = await client.put(
                "/api/users/me",
                json=update_data,
                headers={"Authorization": "Bearer test-token"}
            )

            assert response.status_code == 200
            data = await response.get_json()
            assert "message" in data
            assert data["profile"]["name"] == "Updated Name"


class TestUserProgress:
    """Tests for user progress endpoint."""

    @pytest.mark.asyncio
    async def test_get_user_progress(self, client, onboarded_user):
        """Test retrieval of user progress."""
        onboarded_user.current_streak = 5
        onboarded_user.longest_streak = 10
        onboarded_user.exercises_completed = 25

        with patch('src.middleware.auth_middleware.AuthService.verify_jwt_token') as mock_verify, \
             patch('src.middleware.auth_middleware.AuthService.validate_session') as mock_validate, \
             patch('src.utils.database.get_async_db_session') as mock_db:

            mock_verify.return_value = {
                "user_id": 1,
                "email": "test@example.com",
                "role": "student",
                "jti": "test-jti"
            }
            mock_validate.return_value = True

            # Mock database session
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = onboarded_user
            mock_session.execute.return_value = mock_result
            mock_db.return_value.__aenter__.return_value = mock_session

            response = await client.get(
                "/api/users/me/progress",
                headers={"Authorization": "Bearer test-token"}
            )

            assert response.status_code == 200
            data = await response.get_json()
            assert data["current_streak"] == 5
            assert data["longest_streak"] == 10
            assert data["exercises_completed"] == 25


class TestUserPreferences:
    """Tests for user preferences endpoints."""

    @pytest.mark.asyncio
    async def test_get_user_preferences(self, client, onboarded_user):
        """Test retrieval of user preferences."""
        with patch('src.middleware.auth_middleware.AuthService.verify_jwt_token') as mock_verify, \
             patch('src.middleware.auth_middleware.AuthService.validate_session') as mock_validate, \
             patch('src.utils.database.get_async_db_session') as mock_db:

            mock_verify.return_value = {
                "user_id": 1,
                "email": "test@example.com",
                "role": "student",
                "jti": "test-jti"
            }
            mock_validate.return_value = True

            # Mock database session
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = onboarded_user
            mock_session.execute.return_value = mock_result
            mock_db.return_value.__aenter__.return_value = mock_session

            response = await client.get(
                "/api/users/me/preferences",
                headers={"Authorization": "Bearer test-token"}
            )

            assert response.status_code == 200
            data = await response.get_json()
            assert data["programming_language"] == "python"
            assert data["skill_level"] == "intermediate"
            assert data["learning_style"] == "hands-on"

    @pytest.mark.asyncio
    async def test_update_user_preferences(self, client, onboarded_user):
        """Test updating user preferences."""
        update_data = {
            "programming_language": "javascript",
            "learning_style": "video-based"
        }

        onboarded_user.programming_language = "javascript"
        onboarded_user.learning_style = "video-based"

        with patch('src.middleware.auth_middleware.AuthService.verify_jwt_token') as mock_verify, \
             patch('src.middleware.auth_middleware.AuthService.validate_session') as mock_validate, \
             patch('src.utils.database.get_async_db_session') as mock_db:

            mock_verify.return_value = {
                "user_id": 1,
                "email": "test@example.com",
                "role": "student",
                "jti": "test-jti"
            }
            mock_validate.return_value = True

            # Mock database session
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = onboarded_user
            mock_session.execute.return_value = mock_result
            mock_db.return_value.__aenter__.return_value = mock_session

            response = await client.put(
                "/api/users/me/preferences",
                json=update_data,
                headers={"Authorization": "Bearer test-token"}
            )

            assert response.status_code == 200
            data = await response.get_json()
            assert "message" in data
            assert data["preferences"]["programming_language"] == "javascript"

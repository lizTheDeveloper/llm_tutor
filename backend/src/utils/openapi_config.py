"""
OpenAPI Configuration for Quart-OpenAPI Integration

This module configures OpenAPI 3.0 documentation generation using Quart-OpenAPI.
It provides:
- OpenAPI metadata (title, version, description)
- Security scheme definitions (JWT Bearer)
- Common response schemas
- Swagger UI configuration

Usage:
    from quart_openapi import Pint
    from src.utils.openapi_config import get_openapi_info, get_security_schemes

    app = Pint(__name__, **get_openapi_info())
"""

from typing import Dict, Any


def get_openapi_info() -> Dict[str, Any]:
    """
    Get OpenAPI metadata for Pint initialization.

    Returns:
        Dictionary with OpenAPI info and servers configuration
    """
    return {
        "title": "CodeMentor API",
        "version": "0.1.0",
        "description": """
# CodeMentor API

LLM-powered coding tutor platform providing personalized learning experiences.

## Features

- **Daily Exercises**: Personalized coding challenges based on skill level
- **LLM Tutor**: Interactive chat with AI coding mentor using Socratic method
- **Progress Tracking**: Comprehensive analytics and achievement system
- **Adaptive Difficulty**: Automatic difficulty adjustment based on performance
- **Multi-Language Support**: Python, JavaScript, Java, and more

## Authentication

Most endpoints require JWT authentication. Include the token in the `Authorization` header:

```
Authorization: Bearer <your-jwt-token>
```

Obtain a token by registering and logging in via `/api/auth/register` and `/api/auth/login`.

## Rate Limiting

API endpoints are rate-limited to prevent abuse:
- Chat: 10 requests/min (students), 30 requests/min (admins)
- Exercise Generation: 3 requests/hour (students), 10 requests/hour (admins)
- Hints: 5 requests/hour (students), 15 requests/hour (admins)

## Support

For issues or questions, please visit our GitHub repository.
        """.strip(),
        "contact": {
            "name": "CodeMentor Support",
            "url": "https://github.com/yourusername/llm_tutor",
        },
        "license": {
            "name": "MIT",
            "url": "https://opensource.org/licenses/MIT",
        },
    }


def get_security_schemes() -> Dict[str, Any]:
    """
    Define OpenAPI security schemes.

    Returns:
        Dictionary of security scheme definitions
    """
    return {
        "bearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT token obtained from /api/auth/login or /api/auth/register",
        }
    }


def get_common_schemas() -> Dict[str, Any]:
    """
    Define common OpenAPI schemas used across endpoints.

    Returns:
        Dictionary of reusable schema definitions
    """
    return {
        "Error": {
            "type": "object",
            "properties": {
                "error": {
                    "type": "string",
                    "description": "Error type",
                    "example": "ValidationError"
                },
                "message": {
                    "type": "string",
                    "description": "Human-readable error message",
                    "example": "Invalid email format"
                },
                "status": {
                    "type": "integer",
                    "description": "HTTP status code",
                    "example": 400
                },
                "details": {
                    "type": "object",
                    "description": "Additional error details (optional)",
                    "additionalProperties": True
                }
            },
            "required": ["error", "message", "status"]
        },
        "User": {
            "type": "object",
            "properties": {
                "id": {"type": "integer", "example": 1},
                "email": {"type": "string", "format": "email", "example": "user@example.com"},
                "name": {"type": "string", "example": "John Doe"},
                "role": {"type": "string", "enum": ["Student", "Admin"], "example": "Student"},
                "is_active": {"type": "boolean", "example": True},
                "email_verified": {"type": "boolean", "example": True},
                "onboarding_completed": {"type": "boolean", "example": True},
                "created_at": {"type": "string", "format": "date-time"},
                "updated_at": {"type": "string", "format": "date-time"}
            },
            "required": ["id", "email", "name", "role"]
        },
        "UserProfile": {
            "type": "object",
            "properties": {
                "programming_language": {"type": "string", "example": "Python"},
                "skill_level": {"type": "string", "enum": ["Beginner", "Intermediate", "Advanced"], "example": "Intermediate"},
                "career_goals": {"type": "string", "example": "Become a full-stack developer"},
                "learning_style": {"type": "string", "example": "Visual learner"},
                "time_commitment_hours": {"type": "integer", "minimum": 1, "maximum": 40, "example": 10},
                "bio": {"type": "string", "example": "Aspiring developer passionate about AI"}
            }
        },
        "Exercise": {
            "type": "object",
            "properties": {
                "id": {"type": "integer", "example": 123},
                "title": {"type": "string", "example": "Implement Binary Search"},
                "description": {"type": "string", "example": "Write a function that implements binary search..."},
                "difficulty": {"type": "string", "enum": ["EASY", "MEDIUM", "HARD"], "example": "MEDIUM"},
                "programming_language": {"type": "string", "example": "Python"},
                "exercise_type": {"type": "string", "example": "algorithm"},
                "test_cases": {"type": "array", "items": {"type": "object"}},
                "hints_available": {"type": "integer", "example": 3},
                "estimated_time_minutes": {"type": "integer", "example": 30},
                "created_at": {"type": "string", "format": "date-time"}
            },
            "required": ["id", "title", "description", "difficulty", "programming_language"]
        },
        "ChatMessage": {
            "type": "object",
            "properties": {
                "id": {"type": "integer", "example": 456},
                "conversation_id": {"type": "integer", "example": 789},
                "role": {"type": "string", "enum": ["user", "assistant"], "example": "assistant"},
                "content": {"type": "string", "example": "Let me help you understand recursion..."},
                "created_at": {"type": "string", "format": "date-time"},
                "token_count": {"type": "integer", "example": 150},
                "model_used": {"type": "string", "example": "gpt-3.5-turbo"}
            },
            "required": ["id", "role", "content", "created_at"]
        },
        "ProgressSummary": {
            "type": "object",
            "properties": {
                "total_exercises": {"type": "integer", "example": 42},
                "exercises_completed": {"type": "integer", "example": 35},
                "current_streak": {"type": "integer", "example": 7},
                "longest_streak": {"type": "integer", "example": 14},
                "total_points": {"type": "integer", "example": 1250},
                "skill_levels": {
                    "type": "object",
                    "additionalProperties": {"type": "integer"},
                    "example": {"Python": 75, "JavaScript": 60}
                },
                "badges_earned": {
                    "type": "array",
                    "items": {"type": "string"},
                    "example": ["7_day_streak", "100_exercises"]
                }
            }
        }
    }


def get_common_responses() -> Dict[str, Any]:
    """
    Define common OpenAPI response definitions.

    Returns:
        Dictionary of reusable response definitions
    """
    return {
        "400": {
            "description": "Bad Request - Invalid input parameters",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/Error"},
                    "example": {
                        "error": "ValidationError",
                        "message": "Invalid email format",
                        "status": 400
                    }
                }
            }
        },
        "401": {
            "description": "Unauthorized - Missing or invalid authentication token",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/Error"},
                    "example": {
                        "error": "Unauthorized",
                        "message": "Missing or invalid authentication token",
                        "status": 401
                    }
                }
            }
        },
        "403": {
            "description": "Forbidden - Insufficient permissions or email not verified",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/Error"},
                    "example": {
                        "error": "Forbidden",
                        "message": "Email verification required",
                        "status": 403
                    }
                }
            }
        },
        "404": {
            "description": "Not Found - Resource does not exist",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/Error"},
                    "example": {
                        "error": "Not Found",
                        "message": "Exercise not found",
                        "status": 404
                    }
                }
            }
        },
        "429": {
            "description": "Too Many Requests - Rate limit exceeded",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/Error"},
                    "example": {
                        "error": "RateLimitExceeded",
                        "message": "Rate limit exceeded. Try again in 60 seconds.",
                        "status": 429
                    }
                }
            }
        },
        "500": {
            "description": "Internal Server Error",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/Error"},
                    "example": {
                        "error": "Internal Server Error",
                        "message": "An unexpected error occurred",
                        "status": 500
                    }
                }
            }
        }
    }

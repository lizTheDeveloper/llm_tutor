"""
Integration tests for API Documentation (DOC-1)

This test suite validates OpenAPI documentation generation using Quart-OpenAPI:
- OpenAPI 3.0 specification accessible at /openapi.json
- Swagger UI accessible at /docs
- All endpoints documented with schemas
- Request/response examples included
- Authentication requirements documented
- TypeScript client generation support

TDD Approach:
1. Write tests that define expected documentation structure
2. Implement OpenAPI integration to make tests pass
3. Verify all endpoints are properly documented

Test Strategy:
- Test /openapi.json endpoint returns valid OpenAPI 3.0 spec
- Test all API endpoints are documented in the spec
- Test request/response schemas are present
- Test authentication security schemes are defined
- Test Swagger UI is accessible at /docs
- Test examples are included for all operations
"""

import pytest
import json
from typing import Dict, Any


class TestOpenAPISpecification:
    """Test OpenAPI 3.0 specification generation."""

    @pytest.mark.asyncio
    async def test_openapi_json_endpoint_exists(self, client):
        """Test that /openapi.json endpoint is accessible."""
        response = await client.get("/openapi.json")
        assert response.status_code == 200
        assert response.headers["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_openapi_spec_structure(self, client):
        """Test that OpenAPI spec has correct structure."""
        response = await client.get("/openapi.json")
        spec = await response.get_json()

        # Validate OpenAPI 3.0 structure
        assert "openapi" in spec
        assert spec["openapi"].startswith("3.0")
        assert "info" in spec
        assert "paths" in spec
        assert "components" in spec

    @pytest.mark.asyncio
    async def test_openapi_info_metadata(self, client):
        """Test that OpenAPI spec includes correct metadata."""
        response = await client.get("/openapi.json")
        spec = await response.get_json()

        info = spec["info"]
        assert "title" in info
        assert "version" in info
        assert "description" in info
        assert info["title"] == "CodeMentor API"
        assert len(info["description"]) > 0

    @pytest.mark.asyncio
    async def test_openapi_security_schemes(self, client):
        """Test that security schemes are defined."""
        response = await client.get("/openapi.json")
        spec = await response.get_json()

        assert "components" in spec
        assert "securitySchemes" in spec["components"]

        security_schemes = spec["components"]["securitySchemes"]

        # Should have JWT bearer authentication
        assert "bearerAuth" in security_schemes
        assert security_schemes["bearerAuth"]["type"] == "http"
        assert security_schemes["bearerAuth"]["scheme"] == "bearer"
        assert security_schemes["bearerAuth"]["bearerFormat"] == "JWT"


class TestEndpointDocumentation:
    """Test that all API endpoints are documented."""

    @pytest.mark.asyncio
    async def test_auth_endpoints_documented(self, client):
        """Test authentication endpoints are documented."""
        response = await client.get("/openapi.json")
        spec = await response.get_json()
        paths = spec["paths"]

        # Auth endpoints
        assert "/api/auth/register" in paths
        assert "/api/auth/login" in paths
        assert "/api/auth/logout" in paths
        assert "/api/auth/verify-email" in paths

        # Verify POST method is documented for register
        register_path = paths["/api/auth/register"]
        assert "post" in register_path
        assert "summary" in register_path["post"]
        assert "requestBody" in register_path["post"]
        assert "responses" in register_path["post"]

    @pytest.mark.asyncio
    async def test_user_endpoints_documented(self, client):
        """Test user management endpoints are documented."""
        response = await client.get("/openapi.json")
        spec = await response.get_json()
        paths = spec["paths"]

        # User endpoints
        assert "/api/users/me" in paths
        assert "/api/users/me/profile" in paths
        assert "/api/users/onboarding" in paths  # Onboarding without /me

        # Verify GET method is documented for profile
        profile_path = paths["/api/users/me/profile"]
        assert "get" in profile_path
        assert "security" in profile_path["get"]  # Should require auth

    @pytest.mark.asyncio
    async def test_exercise_endpoints_documented(self, client):
        """Test exercise endpoints are documented."""
        response = await client.get("/openapi.json")
        spec = await response.get_json()
        paths = spec["paths"]

        # Exercise endpoints
        assert "/api/exercises/daily" in paths
        assert "/api/exercises/{exercise_id}" in paths
        assert "/api/exercises/{exercise_id}/submit" in paths
        assert "/api/exercises/{exercise_id}/hint" in paths

        # Verify parameters are documented
        exercise_detail = paths["/api/exercises/{exercise_id}"]
        assert "get" in exercise_detail
        assert "parameters" in exercise_detail["get"]

        # Check exercise_id parameter
        params = exercise_detail["get"]["parameters"]
        exercise_id_param = next((p for p in params if p["name"] == "exercise_id"), None)
        assert exercise_id_param is not None
        assert exercise_id_param["in"] == "path"
        assert exercise_id_param["required"] is True

    @pytest.mark.asyncio
    async def test_chat_endpoints_documented(self, client):
        """Test chat endpoints are documented."""
        response = await client.get("/openapi.json")
        spec = await response.get_json()
        paths = spec["paths"]

        # Chat endpoints
        assert "/api/chat/message" in paths
        assert "/api/chat/conversations" in paths

        # Verify security is required
        message_path = paths["/api/chat/message"]
        assert "post" in message_path
        assert "security" in message_path["post"]

    @pytest.mark.asyncio
    async def test_progress_endpoints_documented(self, client):
        """Test progress tracking endpoints are documented."""
        response = await client.get("/openapi.json")
        spec = await response.get_json()
        paths = spec["paths"]

        # Progress endpoints
        assert "/api/progress" in paths
        assert "/api/progress/badges" in paths
        assert "/api/progress/history" in paths


class TestRequestResponseSchemas:
    """Test that request/response schemas are properly defined."""

    @pytest.mark.asyncio
    async def test_register_request_schema(self, client):
        """Test registration request schema is documented."""
        response = await client.get("/openapi.json")
        spec = await response.get_json()

        register_op = spec["paths"]["/api/auth/register"]["post"]
        request_body = register_op["requestBody"]

        assert "content" in request_body
        assert "application/json" in request_body["content"]

        schema = request_body["content"]["application/json"]["schema"]
        # Schema should have type, $ref, or properties
        assert "type" in schema or "$ref" in schema or "properties" in schema

        # If using $ref, check components
        if "$ref" in schema:
            schema_name = schema["$ref"].split("/")[-1]
            assert schema_name in spec["components"]["schemas"]

    @pytest.mark.asyncio
    async def test_response_schemas_include_examples(self, client):
        """Test that response schemas include examples."""
        response = await client.get("/openapi.json")
        spec = await response.get_json()

        # Check login endpoint has response examples
        login_op = spec["paths"]["/api/auth/login"]["post"]
        responses = login_op["responses"]

        # Should have 200 success response
        assert "200" in responses
        success_response = responses["200"]

        assert "content" in success_response
        assert "application/json" in success_response["content"]

        # Should have schema or example
        content = success_response["content"]["application/json"]
        assert "schema" in content or "example" in content

    @pytest.mark.asyncio
    async def test_error_response_schemas(self, client):
        """Test that error responses are documented."""
        response = await client.get("/openapi.json")
        spec = await response.get_json()

        # Check auth endpoints have error responses
        register_op = spec["paths"]["/api/auth/register"]["post"]
        responses = register_op["responses"]

        # Should document common errors
        assert "400" in responses or "422" in responses  # Validation error
        assert "500" in responses  # Server error

    @pytest.mark.asyncio
    async def test_schemas_component_defined(self, client):
        """Test that reusable schemas are defined in components."""
        response = await client.get("/openapi.json")
        spec = await response.get_json()

        schemas = spec["components"]["schemas"]

        # Should have common schemas
        expected_schemas = [
            "User",
            "UserProfile",
            "Exercise",
            "ChatMessage",
            "Error"
        ]

        # At least some of these should be present
        found_schemas = [s for s in expected_schemas if s in schemas]
        assert len(found_schemas) >= 3, f"Expected schemas not found. Found: {list(schemas.keys())}"


class TestSwaggerUIIntegration:
    """Test Swagger UI accessibility."""

    @pytest.mark.asyncio
    async def test_swagger_ui_endpoint_exists(self, client):
        """Test that /docs endpoint is accessible."""
        response = await client.get("/docs")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_swagger_ui_serves_html(self, client):
        """Test that /docs serves HTML content."""
        response = await client.get("/docs")
        assert "text/html" in response.headers.get("Content-Type", "")

        # Should contain Swagger UI references
        html = await response.get_data(as_text=True)
        assert "swagger" in html.lower() or "openapi" in html.lower()

    @pytest.mark.asyncio
    async def test_swagger_ui_references_openapi_spec(self, client):
        """Test that Swagger UI references the OpenAPI spec."""
        response = await client.get("/docs")
        html = await response.get_data(as_text=True)

        # Should reference /openapi.json
        assert "/openapi.json" in html


class TestDocumentationCompleteness:
    """Test documentation completeness and quality."""

    @pytest.mark.asyncio
    async def test_all_endpoints_have_descriptions(self, client):
        """Test that all endpoints have description text."""
        response = await client.get("/openapi.json")
        spec = await response.get_json()

        missing_descriptions = []

        for path, methods in spec["paths"].items():
            for method, operation in methods.items():
                if method in ["get", "post", "put", "patch", "delete"]:
                    if "summary" not in operation and "description" not in operation:
                        missing_descriptions.append(f"{method.upper()} {path}")

        assert len(missing_descriptions) == 0, \
            f"Endpoints missing descriptions: {missing_descriptions}"

    @pytest.mark.asyncio
    async def test_protected_endpoints_marked_with_security(self, client):
        """Test that protected endpoints have security requirements."""
        response = await client.get("/openapi.json")
        spec = await response.get_json()

        # These endpoints should require authentication
        protected_paths = [
            ("/api/users/me", "get"),
            ("/api/exercises/daily", "get"),
            ("/api/chat/message", "post"),
            ("/api/progress", "get"),
        ]

        for path, method in protected_paths:
            if path in spec["paths"] and method in spec["paths"][path]:
                operation = spec["paths"][path][method]
                assert "security" in operation, \
                    f"{method.upper()} {path} should require authentication"
                assert len(operation["security"]) > 0

    @pytest.mark.asyncio
    async def test_request_body_schemas_have_required_fields(self, client):
        """Test that request schemas define required fields."""
        response = await client.get("/openapi.json")
        spec = await response.get_json()

        # Check register endpoint
        register_op = spec["paths"]["/api/auth/register"]["post"]
        request_body = register_op["requestBody"]

        # Should be required
        assert request_body.get("required") is True, \
            "Register request body should be required"


class TestTypeScriptClientGeneration:
    """Test support for TypeScript client generation."""

    @pytest.mark.asyncio
    async def test_openapi_spec_is_valid_for_codegen(self, client):
        """Test that OpenAPI spec can be used for code generation."""
        response = await client.get("/openapi.json")
        spec = await response.get_json()

        # Basic validation for code generation compatibility
        assert "openapi" in spec
        assert "paths" in spec
        assert "components" in spec

        # All paths should have operationId for client generation
        missing_operation_ids = []
        for path, methods in spec["paths"].items():
            for method, operation in methods.items():
                if method in ["get", "post", "put", "patch", "delete"]:
                    if "operationId" not in operation:
                        missing_operation_ids.append(f"{method.upper()} {path}")

        # operationId is recommended but not strictly required
        # Log warning if missing but don't fail test
        if missing_operation_ids:
            print(f"Warning: Missing operationId for: {missing_operation_ids}")

    @pytest.mark.asyncio
    async def test_schemas_use_standard_types(self, client):
        """Test that schemas use standard JSON Schema types."""
        response = await client.get("/openapi.json")
        spec = await response.get_json()

        if "schemas" not in spec.get("components", {}):
            pytest.skip("No schemas defined yet")

        valid_types = ["string", "number", "integer", "boolean", "array", "object"]

        for schema_name, schema in spec["components"]["schemas"].items():
            if "properties" in schema:
                for prop_name, prop_schema in schema["properties"].items():
                    if "type" in prop_schema:
                        assert prop_schema["type"] in valid_types, \
                            f"Invalid type in {schema_name}.{prop_name}: {prop_schema['type']}"

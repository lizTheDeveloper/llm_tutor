"""
OpenAPI Integration for existing Quart application

This module adds OpenAPI 3.0 documentation to an existing Quart app
without requiring a full rewrite to use Pint class.

It manually constructs the OpenAPI spec from registered routes and
serves it at /openapi.json along with Swagger UI at /docs.
"""

import json
from typing import Dict, Any, List
from quart import Quart, jsonify, render_template_string
from inspect import iscoroutinefunction

from src.utils.openapi_config import (
    get_openapi_info,
    get_security_schemes,
    get_common_schemas,
    get_common_responses
)


SWAGGER_UI_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{{ title }} - Swagger UI</title>
    <link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist@5.10.0/swagger-ui.css">
    <style>
        html { box-sizing: border-box; overflow: -moz-scrollbars-vertical; overflow-y: scroll; }
        *, *:before, *:after { box-sizing: inherit; }
        body { margin:0; padding:0; }
    </style>
</head>
<body>
<div id="swagger-ui"></div>
<script src="https://unpkg.com/swagger-ui-dist@5.10.0/swagger-ui-bundle.js"></script>
<script src="https://unpkg.com/swagger-ui-dist@5.10.0/swagger-ui-standalone-preset.js"></script>
<script>
window.onload = function() {
    window.ui = SwaggerUIBundle({
        url: "{{ spec_url }}",
        dom_id: '#swagger-ui',
        deepLinking: true,
        presets: [
            SwaggerUIBundle.presets.apis,
            SwaggerUIStandalonePreset
        ],
        plugins: [
            SwaggerUIBundle.plugins.DownloadUrl
        ],
        layout: "StandaloneLayout"
    });
};
</script>
</body>
</html>
"""


def generate_openapi_spec(app: Quart) -> Dict[str, Any]:
    """
    Generate OpenAPI 3.0 specification from Quart app routes.

    Args:
        app: Quart application instance

    Returns:
        OpenAPI 3.0 specification dictionary
    """
    info_config = get_openapi_info()

    spec = {
        "openapi": "3.0.3",
        "info": {
            "title": info_config["title"],
            "version": info_config["version"],
            "description": info_config["description"],
            "contact": info_config.get("contact", {}),
            "license": info_config.get("license", {}),
        },
        "servers": [
            {
                "url": "/api",
                "description": "API Server"
            }
        ],
        "paths": {},
        "components": {
            "securitySchemes": get_security_schemes(),
            "schemas": get_common_schemas(),
            "responses": get_common_responses()
        },
        "tags": [
            {"name": "Authentication", "description": "User authentication and authorization"},
            {"name": "Users", "description": "User profile and onboarding"},
            {"name": "Exercises", "description": "Daily coding exercises and submissions"},
            {"name": "Chat", "description": "LLM tutor chat interface"},
            {"name": "Progress", "description": "Progress tracking and achievements"},
            {"name": "GitHub", "description": "GitHub integration"},
            {"name": "Health", "description": "Service health checks"},
        ]
    }

    # Extract paths from app routes
    spec["paths"] = extract_paths_from_routes(app)

    return spec


def extract_paths_from_routes(app: Quart) -> Dict[str, Any]:
    """
    Extract OpenAPI paths from Quart app routes.

    Args:
        app: Quart application instance

    Returns:
        Dictionary of OpenAPI path definitions
    """
    paths = {}

    # Iterate through app URL map
    for rule in app.url_map.iter_rules():
        # Skip static and internal routes
        if rule.endpoint.startswith('static') or rule.endpoint.startswith('_'):
            continue

        # Get the route path (OpenAPI format)
        # Convert Flask/Quart route syntax to OpenAPI syntax
        # <int:id> -> {id}, <string:name> -> {name}, etc.
        import re
        path = rule.rule
        path = re.sub(r'<(?:int|string|float|path|uuid):([^>]+)>', r'{\1}', path)
        path = re.sub(r'<([^>]+)>', r'{\1}', path)  # Handle non-typed parameters

        # Get HTTP methods
        methods = [m.lower() for m in rule.methods if m not in ['HEAD', 'OPTIONS']]

        # Skip if no valid methods
        if not methods:
            continue

        # Initialize path if not exists
        if path not in paths:
            paths[path] = {}

        # Get view function
        view_func = app.view_functions.get(rule.endpoint)
        if not view_func:
            continue

        # Extract documentation from docstring
        docstring = view_func.__doc__ or ""
        summary, description = parse_docstring(docstring)

        # Determine tag from path
        tag = determine_tag_from_path(path)

        # Determine if endpoint requires authentication
        requires_auth = requires_authentication(path)

        # Add operation for each method
        for method in methods:
            operation = {
                "tags": [tag],
                "summary": summary or f"{method.upper()} {path}",
                "description": description or "No description available",
                "operationId": f"{method}_{rule.endpoint}",
                "responses": {
                    "200": {
                        "description": "Successful operation",
                        "content": {
                            "application/json": {
                                "schema": {"type": "object"}
                            }
                        }
                    },
                    **get_common_error_responses()
                }
            }

            # Add security requirement if needed
            if requires_auth:
                operation["security"] = [{"bearerAuth": []}]

            # Add path parameters
            parameters = extract_path_parameters(path)
            if parameters:
                operation["parameters"] = parameters

            # Add request body for POST/PUT/PATCH
            if method in ['post', 'put', 'patch']:
                operation["requestBody"] = {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"type": "object"}
                        }
                    }
                }

            paths[path][method] = operation

    return paths


def parse_docstring(docstring: str) -> tuple[str, str]:
    """
    Parse docstring into summary and description.

    Args:
        docstring: Function docstring

    Returns:
        Tuple of (summary, description)
    """
    lines = [line.strip() for line in docstring.strip().split('\n') if line.strip()]

    if not lines:
        return "", ""

    summary = lines[0]
    description = '\n'.join(lines[1:]) if len(lines) > 1 else ""

    return summary, description


def determine_tag_from_path(path: str) -> str:
    """
    Determine OpenAPI tag from path.

    Args:
        path: URL path

    Returns:
        Tag name
    """
    if '/auth' in path:
        return "Authentication"
    elif '/users' in path:
        return "Users"
    elif '/exercises' in path:
        return "Exercises"
    elif '/chat' in path:
        return "Chat"
    elif '/progress' in path:
        return "Progress"
    elif '/github' in path:
        return "GitHub"
    elif '/health' in path:
        return "Health"
    else:
        return "Other"


def requires_authentication(path: str) -> bool:
    """
    Determine if endpoint requires authentication.

    Args:
        path: URL path

    Returns:
        True if authentication is required
    """
    # Public endpoints (exact matches)
    public_exact = [
        '/health',
        '/metrics',
        '/',
        '/openapi.json',
        '/docs',
        '/api/auth/register',
        '/api/auth/login',
        '/api/auth/verify-email',
        '/api/auth/resend-verification',
        '/api/auth/forgot-password',
        '/api/auth/reset-password',
        '/api/users/onboarding/questions',
        '/api/users/onboarding/status',
    ]

    # Public endpoint prefixes
    public_prefixes = [
        '/api/auth/oauth/',  # OAuth endpoints
    ]

    # Check if path exactly matches public endpoint
    if path in public_exact:
        return False

    # Check if path starts with a public prefix
    for public_prefix in public_prefixes:
        if path.startswith(public_prefix):
            return False

    # All other API endpoints require auth
    return path.startswith('/api/')


def extract_path_parameters(path: str) -> List[Dict[str, Any]]:
    """
    Extract path parameters from OpenAPI path.

    Args:
        path: OpenAPI path with {param} syntax

    Returns:
        List of parameter definitions
    """
    import re

    parameters = []
    param_pattern = r'\{([^}]+)\}'

    for match in re.finditer(param_pattern, path):
        param_name = match.group(1)
        parameters.append({
            "name": param_name,
            "in": "path",
            "required": True,
            "schema": {"type": "string"},
            "description": f"{param_name.replace('_', ' ').title()} identifier"
        })

    return parameters


def get_common_error_responses() -> Dict[str, Any]:
    """
    Get common error response references.

    Returns:
        Dictionary of error response references
    """
    return {
        "400": {"$ref": "#/components/responses/400"},
        "401": {"$ref": "#/components/responses/401"},
        "500": {"$ref": "#/components/responses/500"}
    }


def add_openapi_routes(app: Quart) -> None:
    """
    Add OpenAPI documentation routes to Quart app.

    Adds:
    - /openapi.json - OpenAPI 3.0 specification
    - /docs - Swagger UI

    Args:
        app: Quart application instance
    """

    @app.route("/openapi.json", methods=["GET"])
    async def openapi_spec():
        """
        Get OpenAPI 3.0 specification.

        Returns:
            JSON OpenAPI specification
        """
        spec = generate_openapi_spec(app)
        return jsonify(spec)

    @app.route("/docs", methods=["GET"])
    async def swagger_ui():
        """
        Serve Swagger UI for API documentation.

        Returns:
            HTML page with Swagger UI
        """
        info_config = get_openapi_info()
        return await render_template_string(
            SWAGGER_UI_HTML,
            title=info_config["title"],
            spec_url="/openapi.json"
        )

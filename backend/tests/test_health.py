"""
Tests for health check API endpoints.
"""
import pytest
from quart import Quart


@pytest.mark.asyncio
async def test_health_check(client):
    """
    Test GET /api/health/ returns healthy status.
    """
    response = await client.get("/api/health/")
    assert response.status_code == 200

    data = await response.get_json()
    assert data["status"] == "healthy"
    assert "checks" in data
    assert "database" in data["checks"]
    assert "redis" in data["checks"]
    assert "llm_service" in data["checks"]


@pytest.mark.asyncio
async def test_readiness_check(client):
    """
    Test GET /api/health/ready returns ready status.
    """
    response = await client.get("/api/health/ready")
    assert response.status_code == 200

    data = await response.get_json()
    assert data["status"] == "ready"
    assert "dependencies" in data
    assert "database" in data["dependencies"]
    assert "redis" in data["dependencies"]


@pytest.mark.asyncio
async def test_liveness_check(client):
    """
    Test GET /api/health/live returns alive status.
    """
    response = await client.get("/api/health/live")
    assert response.status_code == 200

    data = await response.get_json()
    assert data["status"] == "alive"

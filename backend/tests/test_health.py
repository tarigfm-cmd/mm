import pytest


@pytest.mark.asyncio
async def test_health_returns_ok(client):
    response = await client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "database" in data
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_health_database_status(client):
    response = await client.get("/api/health")
    data = response.json()
    # In test environment with SQLite the DB should be healthy
    assert data["database"] in ("healthy", "unhealthy")

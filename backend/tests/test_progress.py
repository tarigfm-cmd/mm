"""Integration tests for GET /api/progress."""
import pytest
from httpx import AsyncClient

USER = {
    "email": "progress@example.com",
    "username": "progressuser",
    "password": "ProgPass1!",
}


async def _register_and_login(client: AsyncClient) -> str:
    await client.post("/api/auth/register", json=USER)
    resp = await client.post("/api/auth/login", json={
        "email": USER["email"],
        "password": USER["password"],
    })
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_progress_requires_auth(client: AsyncClient):
    resp = await client.get("/api/progress")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_progress_returns_correct_shape(client: AsyncClient):
    token = await _register_and_login(client)
    resp = await client.get("/api/progress", headers=_auth(token))

    assert resp.status_code == 200
    data = resp.json()
    assert "total_attempts" in data
    assert "avg_score" in data
    assert "best_score" in data
    assert "score_trend" in data
    assert "by_difficulty" in data
    assert "by_specialty" in data
    assert isinstance(data["score_trend"], list)
    assert isinstance(data["by_difficulty"], list)
    assert isinstance(data["by_specialty"], list)


@pytest.mark.asyncio
async def test_progress_no_attempts_returns_zeros(client: AsyncClient):
    token = await _register_and_login(client)
    resp = await client.get("/api/progress", headers=_auth(token))

    data = resp.json()
    assert data["total_attempts"] == 0
    assert data["avg_score"] is None
    assert data["best_score"] is None
    assert data["score_trend"] == []
    assert data["by_difficulty"] == []
    assert data["by_specialty"] == []


@pytest.mark.asyncio
async def test_progress_days_param_accepted(client: AsyncClient):
    token = await _register_and_login(client)
    for days in [7, 14, 90]:
        resp = await client.get(f"/api/progress?days={days}", headers=_auth(token))
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_progress_invalid_days_rejected(client: AsyncClient):
    token = await _register_and_login(client)
    resp = await client.get("/api/progress?days=0", headers=_auth(token))
    assert resp.status_code == 422
    resp = await client.get("/api/progress?days=366", headers=_auth(token))
    assert resp.status_code == 422

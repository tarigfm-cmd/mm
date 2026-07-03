"""
Tests for scenario endpoints that do not require the AI service.
Scenarios and interactions are inserted directly into the test DB.
"""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.learning import Interaction, Scenario


async def _create_scenario(engine) -> uuid.UUID:
    """Insert a minimal Scenario directly, bypassing the AI generate endpoint."""
    scenario_id = uuid.uuid4()
    async with AsyncSession(engine, expire_on_commit=False) as s:
        s.add(
            Scenario(
                id=scenario_id,
                title="Test Pharmacy Case",
                clinical_case="A patient presents with symptoms of X.",
                difficulty_level="intermediate",
                expected_answer="Recommend Y and counsel on Z.",
            )
        )
        await s.commit()
    return scenario_id


async def _add_interactions(engine, scenario_id: uuid.UUID, n: int) -> None:
    async with AsyncSession(engine, expire_on_commit=False) as s:
        for _ in range(n):
            s.add(
                Interaction(
                    scenario_id=scenario_id,
                    session_id=str(uuid.uuid4()),
                    user_answer="My attempt at an answer.",
                    ai_feedback="Good effort.",
                    score=0.75,
                )
            )
        await s.commit()


# ── GET /api/scenarios/{id} interaction_count ─────────────────────────────────


@pytest.mark.asyncio
async def test_get_scenario_interaction_count_zero(client: AsyncClient, fresh_engine):
    """get_scenario returns interaction_count=0 when no interactions exist."""
    scenario_id = await _create_scenario(fresh_engine)
    resp = await client.get(f"/api/scenarios/{scenario_id}")
    assert resp.status_code == 200
    assert resp.json()["interaction_count"] == 0


@pytest.mark.asyncio
async def test_get_scenario_interaction_count_accurate(client: AsyncClient, fresh_engine):
    """get_scenario returns the real interaction count, not always 0."""
    scenario_id = await _create_scenario(fresh_engine)
    await _add_interactions(fresh_engine, scenario_id, 3)
    resp = await client.get(f"/api/scenarios/{scenario_id}")
    assert resp.status_code == 200
    assert resp.json()["interaction_count"] == 3


@pytest.mark.asyncio
async def test_get_scenario_not_found_returns_404(client: AsyncClient, fresh_engine):
    resp = await client.get(f"/api/scenarios/{uuid.uuid4()}")
    assert resp.status_code == 404


# ── GET /api/scenarios list interaction_count ─────────────────────────────────


@pytest.mark.asyncio
async def test_list_scenarios_interaction_count_accurate(client: AsyncClient, fresh_engine):
    """list_scenarios batch-counts interactions correctly."""
    scenario_id = await _create_scenario(fresh_engine)
    await _add_interactions(fresh_engine, scenario_id, 2)

    resp = await client.get("/api/scenarios")
    assert resp.status_code == 200
    items = resp.json()["items"]
    target = next(i for i in items if i["id"] == str(scenario_id))
    assert target["interaction_count"] == 2


@pytest.mark.asyncio
async def test_list_scenarios_returns_correct_shape(client: AsyncClient, fresh_engine):
    resp = await client.get("/api/scenarios")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "per_page" in data
    assert "pages" in data


@pytest.mark.asyncio
async def test_list_scenarios_filters_by_difficulty(client: AsyncClient, fresh_engine):
    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        s.add(Scenario(
            title="Beginner Case",
            clinical_case="A simple case.",
            difficulty_level="beginner",
            expected_answer="Basic answer.",
        ))
        s.add(Scenario(
            title="Advanced Case",
            clinical_case="A complex case.",
            difficulty_level="advanced",
            expected_answer="Complex answer.",
        ))
        await s.commit()

    resp = await client.get("/api/scenarios?difficulty=beginner")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert all(i["difficulty_level"] == "beginner" for i in items)

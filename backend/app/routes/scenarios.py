import math
import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import get_optional_user
from app.database import get_db
from app.models import Interaction, Material, Scenario
from app.schemas import (
    InteractionCreate,
    InteractionResponse,
    ScenarioGenerateRequest,
    ScenarioInteractionsResponse,
    ScenarioListItem,
    ScenarioListResponse,
    ScenarioResponse,
)
from app.services.ai_service import evaluate_answer, generate_scenario

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])


@router.post(
    "/generate",
    response_model=ScenarioResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a new clinical scenario from a material",
)
async def generate_scenario_endpoint(
    request: ScenarioGenerateRequest,
    db: AsyncSession = Depends(get_db),
) -> ScenarioResponse:
    # Verify material exists and has extractable content
    material = await db.get(Material, request.material_id)
    if material is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found.")
    if not material.content_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Material content has not been extracted yet. "
                "Please wait a moment and try again, or re-upload the file."
            ),
        )

    try:
        ai_result = generate_scenario(
            content_text=material.content_text,
            difficulty_level=request.difficulty_level,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    scenario = Scenario(
        material_id=material.id,
        title=ai_result["title"],
        clinical_case=ai_result["clinical_case"],
        difficulty_level=request.difficulty_level,
        specialty=ai_result.get("specialty") or request.specialty,
        key_concepts=ai_result.get("key_concepts"),
        expected_answer=ai_result.get("expected_answer"),
    )
    db.add(scenario)
    await db.commit()
    await db.refresh(scenario)

    return ScenarioResponse.model_validate(scenario)


@router.get(
    "",
    response_model=ScenarioListResponse,
    summary="List all scenarios",
)
async def list_scenarios(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    difficulty: Optional[str] = Query(default=None),
    material_id: Optional[uuid.UUID] = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> ScenarioListResponse:
    query = select(Scenario)
    count_query = select(func.count(Scenario.id))

    if difficulty:
        query = query.where(Scenario.difficulty_level == difficulty.lower())
        count_query = count_query.where(Scenario.difficulty_level == difficulty.lower())
    if material_id:
        query = query.where(Scenario.material_id == material_id)
        count_query = count_query.where(Scenario.material_id == material_id)

    total: int = (await db.execute(count_query)).scalar_one()

    offset = (page - 1) * per_page
    scenarios = (
        await db.execute(query.order_by(Scenario.created_at.desc()).offset(offset).limit(per_page))
    ).scalars().all()

    # Batch-load interaction counts
    interaction_counts = {}
    if scenarios:
        ids = [s.id for s in scenarios]
        counts_result = await db.execute(
            select(Interaction.scenario_id, func.count(Interaction.id).label("count"))
            .where(Interaction.scenario_id.in_(ids))
            .group_by(Interaction.scenario_id)
        )
        interaction_counts = {row.scenario_id: row.count for row in counts_result}

    items = [
        ScenarioListItem(
            id=s.id,
            material_id=s.material_id,
            title=s.title,
            difficulty_level=s.difficulty_level,
            specialty=s.specialty,
            key_concepts=s.key_concepts,
            interaction_count=interaction_counts.get(s.id, 0),
            created_at=s.created_at,
        )
        for s in scenarios
    ]

    return ScenarioListResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        pages=math.ceil(total / per_page) if total else 0,
    )


@router.get(
    "/{scenario_id}",
    response_model=ScenarioResponse,
    summary="Get a specific scenario by ID",
)
async def get_scenario(
    scenario_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ScenarioResponse:
    scenario = await db.get(Scenario, scenario_id)
    if scenario is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found.")
    return ScenarioResponse.model_validate(scenario)


@router.post(
    "/{scenario_id}/answer",
    response_model=InteractionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit an answer to a scenario and receive AI feedback",
)
async def submit_answer(
    scenario_id: uuid.UUID,
    body: InteractionCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_optional_user),
) -> InteractionResponse:
    scenario = await db.get(Scenario, scenario_id)
    if scenario is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found.")

    # Override scenario_id from path (path is authoritative)
    if body.scenario_id != scenario_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="scenario_id in body must match the URL path parameter.",
        )

    try:
        evaluation = evaluate_answer(
            clinical_case=scenario.clinical_case,
            expected_answer=scenario.expected_answer or "",
            user_answer=body.content,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    interaction = Interaction(
        scenario_id=scenario.id,
        session_id=body.session_id,
        user_id=current_user.id if current_user else None,
        user_answer=body.content,
        ai_feedback=evaluation["feedback"],
        score=evaluation["score"],
        key_findings=evaluation.get("key_findings"),
        next_steps=evaluation.get("next_steps"),
        strengths=evaluation.get("strengths"),
        areas_for_improvement=evaluation.get("areas_for_improvement"),
    )
    db.add(interaction)
    await db.commit()
    await db.refresh(interaction)

    return InteractionResponse.model_validate(interaction)


@router.get(
    "/{scenario_id}/interactions",
    response_model=ScenarioInteractionsResponse,
    summary="Get all interactions for a scenario",
)
async def get_scenario_interactions(
    scenario_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ScenarioInteractionsResponse:
    result = await db.execute(
        select(Scenario)
        .where(Scenario.id == scenario_id)
        .options(selectinload(Scenario.interactions))
    )
    scenario = result.scalar_one_or_none()
    if scenario is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found.")

    interactions = sorted(scenario.interactions, key=lambda i: i.created_at)
    scores = [i.score for i in interactions if i.score is not None]
    avg_score = sum(scores) / len(scores) if scores else None

    return ScenarioInteractionsResponse(
        scenario=ScenarioResponse.model_validate(scenario),
        interactions=[InteractionResponse.model_validate(i) for i in interactions],
        average_score=avg_score,
        total_interactions=len(interactions),
    )

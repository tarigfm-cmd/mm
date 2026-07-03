"""Progress tracking endpoints — per-user learning analytics."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.learning import Interaction, Scenario

router = APIRouter(prefix="/api/progress", tags=["progress"])


class ScorePoint(BaseModel):
    date: str
    avg_score: float
    count: int


class BreakdownItem(BaseModel):
    label: str
    avg_score: float
    count: int


class ProgressSummary(BaseModel):
    total_attempts: int
    avg_score: float | None
    best_score: float | None
    score_trend: list[ScorePoint]
    by_difficulty: list[BreakdownItem]
    by_specialty: list[BreakdownItem]


@router.get("", response_model=ProgressSummary, summary="Get learning progress for the current user")
async def get_progress(
    days: int = Query(default=30, ge=1, le=365, description="Look-back window in days"),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProgressSummary:
    since = datetime.now(timezone.utc) - timedelta(days=days)

    # ── aggregate totals ──────────────────────────────────────────────────────
    totals_result = await db.execute(
        select(
            func.count(Interaction.id).label("total"),
            func.avg(Interaction.score).label("avg_score"),
            func.max(Interaction.score).label("best_score"),
        ).where(
            Interaction.user_id == current_user.id,
            Interaction.created_at >= since,
        )
    )
    totals = totals_result.one()

    # ── daily trend ───────────────────────────────────────────────────────────
    # SQLite-compatible: use strftime; Postgres: date_trunc. Both supported via func.date.
    trend_result = await db.execute(
        select(
            func.date(Interaction.created_at).label("day"),
            func.avg(Interaction.score).label("avg_score"),
            func.count(Interaction.id).label("count"),
        )
        .where(
            Interaction.user_id == current_user.id,
            Interaction.created_at >= since,
            Interaction.score.is_not(None),
        )
        .group_by(func.date(Interaction.created_at))
        .order_by(func.date(Interaction.created_at))
    )
    trend = [
        ScorePoint(date=str(row.day), avg_score=round(row.avg_score, 2), count=row.count)
        for row in trend_result
    ]

    # ── by difficulty ─────────────────────────────────────────────────────────
    diff_result = await db.execute(
        select(
            Scenario.difficulty_level.label("label"),
            func.avg(Interaction.score).label("avg_score"),
            func.count(Interaction.id).label("count"),
        )
        .join(Scenario, Interaction.scenario_id == Scenario.id)
        .where(
            Interaction.user_id == current_user.id,
            Interaction.created_at >= since,
            Interaction.score.is_not(None),
        )
        .group_by(Scenario.difficulty_level)
        .order_by(func.avg(Interaction.score).desc())
    )
    by_difficulty = [
        BreakdownItem(label=row.label, avg_score=round(row.avg_score, 2), count=row.count)
        for row in diff_result
    ]

    # ── by specialty ──────────────────────────────────────────────────────────
    spec_result = await db.execute(
        select(
            Scenario.specialty.label("label"),
            func.avg(Interaction.score).label("avg_score"),
            func.count(Interaction.id).label("count"),
        )
        .join(Scenario, Interaction.scenario_id == Scenario.id)
        .where(
            Interaction.user_id == current_user.id,
            Interaction.created_at >= since,
            Interaction.score.is_not(None),
            Scenario.specialty.is_not(None),
        )
        .group_by(Scenario.specialty)
        .order_by(func.avg(Interaction.score).desc())
    )
    by_specialty = [
        BreakdownItem(label=row.label, avg_score=round(row.avg_score, 2), count=row.count)
        for row in spec_result
    ]

    return ProgressSummary(
        total_attempts=totals.total or 0,
        avg_score=round(totals.avg_score, 2) if totals.avg_score is not None else None,
        best_score=round(totals.best_score, 2) if totals.best_score is not None else None,
        score_trend=trend,
        by_difficulty=by_difficulty,
        by_specialty=by_specialty,
    )

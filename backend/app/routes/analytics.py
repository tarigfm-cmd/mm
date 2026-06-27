"""Learner failure analytics routes."""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, require_superuser
from app.database import get_db
from app.models.governance import ContentItem, LearnerFailureAnalytics
from app.models.identity import User
from app.schemas.governance import (
    ContentFailureSummary,
    FailureAnalyticsCreate,
    FailureHotspot,
    OrgWeaknessMap,
)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

_FAILURE_COLUMNS = {
    "failed_red_flag": LearnerFailureAnalytics.failed_red_flag,
    "failed_counseling_point": LearnerFailureAnalytics.failed_counseling_point,
    "failed_interaction_detection": LearnerFailureAnalytics.failed_interaction_detection,
    "failed_referral_decision": LearnerFailureAnalytics.failed_referral_decision,
    "failed_dose_calculation": LearnerFailureAnalytics.failed_dose_calculation,
    "failed_documentation": LearnerFailureAnalytics.failed_documentation,
}


@router.post("/failures", status_code=status.HTTP_201_CREATED)
async def record_failure(
    body: FailureAnalyticsCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Record a learner attempt outcome against a content item."""
    # Verify content item exists
    item = await db.get(ContentItem, body.content_item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Content item not found")

    record = LearnerFailureAnalytics(
        user_id=current_user.id,
        **body.model_dump(),
    )
    db.add(record)
    await db.commit()
    return {"id": str(record.id)}


@router.get("/failure-hotspots", response_model=list[FailureHotspot])
async def get_failure_hotspots(
    region_code: Optional[str] = Query(None),
    content_type: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_superuser),
):
    q = (
        select(
            ContentItem.id,
            ContentItem.title,
            ContentItem.content_type,
            func.count(LearnerFailureAnalytics.id).label("total_attempts"),
            func.avg(LearnerFailureAnalytics.score).label("avg_score"),
            func.avg(func.cast(LearnerFailureAnalytics.failed_red_flag, type_=func.count().type)).label("red_flag_fail_rate"),
            func.avg(func.cast(LearnerFailureAnalytics.failed_counseling_point, type_=func.count().type)).label("counseling_fail_rate"),
            func.avg(func.cast(LearnerFailureAnalytics.failed_interaction_detection, type_=func.count().type)).label("interaction_fail_rate"),
            func.avg(func.cast(LearnerFailureAnalytics.failed_referral_decision, type_=func.count().type)).label("referral_fail_rate"),
            func.avg(func.cast(LearnerFailureAnalytics.failed_dose_calculation, type_=func.count().type)).label("dose_calc_fail_rate"),
            func.avg(func.cast(LearnerFailureAnalytics.failed_documentation, type_=func.count().type)).label("documentation_fail_rate"),
        )
        .join(LearnerFailureAnalytics, LearnerFailureAnalytics.content_item_id == ContentItem.id)
        .group_by(ContentItem.id, ContentItem.title, ContentItem.content_type)
        .order_by(func.count(LearnerFailureAnalytics.id).desc())
        .limit(limit)
    )

    if region_code:
        q = q.where(LearnerFailureAnalytics.region_code == region_code)
    if content_type:
        q = q.where(ContentItem.content_type == content_type)

    rows = (await db.execute(q)).all()

    return [
        FailureHotspot(
            content_item_id=r.id,
            title=r.title,
            content_type=r.content_type,
            total_attempts=r.total_attempts,
            avg_score=r.avg_score,
            red_flag_fail_rate=float(r.red_flag_fail_rate or 0),
            counseling_fail_rate=float(r.counseling_fail_rate or 0),
            interaction_fail_rate=float(r.interaction_fail_rate or 0),
            referral_fail_rate=float(r.referral_fail_rate or 0),
            dose_calc_fail_rate=float(r.dose_calc_fail_rate or 0),
            documentation_fail_rate=float(r.documentation_fail_rate or 0),
        )
        for r in rows
    ]


@router.get("/content/{item_id}/failure-summary", response_model=ContentFailureSummary)
async def get_content_failure_summary(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_superuser),
):
    item = await db.get(ContentItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Content item not found")

    # Aggregate totals
    agg = (await db.execute(
        select(
            func.count(LearnerFailureAnalytics.id).label("total"),
            func.avg(LearnerFailureAnalytics.score).label("avg_score"),
            func.sum(func.cast(LearnerFailureAnalytics.failed_red_flag, type_=func.count().type)).label("red_flag"),
            func.sum(func.cast(LearnerFailureAnalytics.failed_counseling_point, type_=func.count().type)).label("counseling"),
            func.sum(func.cast(LearnerFailureAnalytics.failed_interaction_detection, type_=func.count().type)).label("interaction"),
            func.sum(func.cast(LearnerFailureAnalytics.failed_referral_decision, type_=func.count().type)).label("referral"),
            func.sum(func.cast(LearnerFailureAnalytics.failed_dose_calculation, type_=func.count().type)).label("dose_calc"),
            func.sum(func.cast(LearnerFailureAnalytics.failed_documentation, type_=func.count().type)).label("documentation"),
        ).where(LearnerFailureAnalytics.content_item_id == item_id)
    )).one()

    total = agg.total or 0
    failure_breakdown = {}
    if total:
        failure_breakdown = {
            "red_flag": float(agg.red_flag or 0) / total,
            "counseling_point": float(agg.counseling or 0) / total,
            "interaction_detection": float(agg.interaction or 0) / total,
            "referral_decision": float(agg.referral or 0) / total,
            "dose_calculation": float(agg.dose_calc or 0) / total,
            "documentation": float(agg.documentation or 0) / total,
        }

    # Per-version breakdown
    version_rows = (await db.execute(
        select(
            LearnerFailureAnalytics.content_version_id,
            func.count(LearnerFailureAnalytics.id).label("attempts"),
            func.avg(LearnerFailureAnalytics.score).label("avg_score"),
        )
        .where(LearnerFailureAnalytics.content_item_id == item_id)
        .group_by(LearnerFailureAnalytics.content_version_id)
    )).all()

    version_breakdown = [
        {
            "content_version_id": str(r.content_version_id) if r.content_version_id else None,
            "attempts": r.attempts,
            "avg_score": float(r.avg_score) if r.avg_score is not None else None,
        }
        for r in version_rows
    ]

    return ContentFailureSummary(
        content_item_id=item_id,
        title=item.title,
        total_attempts=total,
        avg_score=float(agg.avg_score) if agg.avg_score is not None else None,
        failure_breakdown=failure_breakdown,
        version_breakdown=version_breakdown,
    )


@router.get("/organization/{org_id}/weakness-map", response_model=OrgWeaknessMap)
async def get_org_weakness_map(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_superuser),
):
    agg = (await db.execute(
        select(
            func.count(LearnerFailureAnalytics.id).label("total"),
            func.sum(func.cast(LearnerFailureAnalytics.failed_red_flag, type_=func.count().type)).label("red_flag"),
            func.sum(func.cast(LearnerFailureAnalytics.failed_counseling_point, type_=func.count().type)).label("counseling"),
            func.sum(func.cast(LearnerFailureAnalytics.failed_interaction_detection, type_=func.count().type)).label("interaction"),
            func.sum(func.cast(LearnerFailureAnalytics.failed_referral_decision, type_=func.count().type)).label("referral"),
            func.sum(func.cast(LearnerFailureAnalytics.failed_dose_calculation, type_=func.count().type)).label("dose_calc"),
            func.sum(func.cast(LearnerFailureAnalytics.failed_documentation, type_=func.count().type)).label("documentation"),
        ).where(LearnerFailureAnalytics.organization_id == org_id)
    )).one()

    total = agg.total or 0
    failure_rates: dict[str, float] = {}
    if total:
        failure_rates = {
            "red_flag": float(agg.red_flag or 0) / total,
            "counseling_point": float(agg.counseling or 0) / total,
            "interaction_detection": float(agg.interaction or 0) / total,
            "referral_decision": float(agg.referral or 0) / total,
            "dose_calculation": float(agg.dose_calc or 0) / total,
            "documentation": float(agg.documentation or 0) / total,
        }

    top_failure_types = sorted(failure_rates, key=lambda k: failure_rates[k], reverse=True)[:3]

    # Identify weak domains (domains where avg score is below 0.6)
    domain_rows = (await db.execute(
        select(
            ContentItem.domain,
            func.avg(LearnerFailureAnalytics.score).label("avg_score"),
        )
        .join(ContentItem, ContentItem.id == LearnerFailureAnalytics.content_item_id)
        .where(
            LearnerFailureAnalytics.organization_id == org_id,
            ContentItem.domain != None,  # noqa: E711
        )
        .group_by(ContentItem.domain)
        .having(func.avg(LearnerFailureAnalytics.score) < 0.6)
        .order_by(func.avg(LearnerFailureAnalytics.score).asc())
    )).all()

    weak_domains = [r.domain for r in domain_rows if r.domain]

    return OrgWeaknessMap(
        organization_id=org_id,
        top_failure_types=top_failure_types,
        failure_rates=failure_rates,
        weak_domains=weak_domains,
        total_attempts=total,
    )

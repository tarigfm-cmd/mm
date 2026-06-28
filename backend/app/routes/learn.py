"""Learner-facing published content routes.

Security contract:
- Only content with an active PublicationRecord (status='published') is returned.
- Answer/scoring keys are stripped from the detail payload before returning.
- Attempt analytics are scoped to current_user.id — no cross-user data.
- Admin metadata (created_by, content_hash, source_file, reviewer internals)
  is never included in any response schema on this router.
"""
import math
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import cast, func, or_, select
from sqlalchemy import Integer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.governance import (
    CONTENT_TYPES,
    REGION_CODES,
    ContentItem,
    ContentVersion,
    LearnerFailureAnalytics,
    PublicationRecord,
    RegionPublishingRule,
)
from app.models.identity import User
from app.schemas.learn import (
    LearnableContentDetail,
    LearnableContentItem,
    LearnableContentListResponse,
    LearnerAttemptCreate,
    LearnerAttemptResult,
    LearnerProgressSummary,
    LearnerRecentAttempt,
)

router = APIRouter(prefix="/api/learn", tags=["learner"])

# Keys that must never be returned to learners before they submit an attempt.
_ANSWER_KEYS = frozenset({
    "correct_answer_or_expected_response",
    "expected_decision",
    "expected_pharmacist_action",
    "hidden_risk",
    "failure_mode",
    "critical_fail",
    "scoring_rubric",
})


def _strip_answer_keys(payload: dict | None) -> dict | None:
    """Return payload with answer/scoring fields removed."""
    if not payload:
        return payload
    return {k: v for k, v in payload.items() if k not in _ANSWER_KEYS}


def _score_attempt(
    content_type: str,
    payload: dict | None,
    body: LearnerAttemptCreate,
) -> tuple[float | None, str, list[str]]:
    """Deterministic scoring against structured payload fields.

    Returns (score, feedback, failed_dimensions).
    score=None means no automated scoring is possible — attempt is still recorded.
    """
    if not payload:
        return (
            None,
            "Your attempt has been recorded. Feedback requires supervisor review.",
            [],
        )

    failed: list[str] = []

    # Drill: exact-match on correct_answer_or_expected_response
    correct = payload.get("correct_answer_or_expected_response")
    if correct is not None and body.learner_response is not None:
        if str(body.learner_response).strip().lower() == str(correct).strip().lower():
            return 1.0, "Correct! Your answer matches the expected response.", []
        else:
            return (
                0.0,
                f"Incorrect. The expected response was: {correct}",
                ["response_mismatch"],
            )

    # Case: expected_decision
    expected_decision = payload.get("expected_decision")
    if expected_decision is not None and body.selected_action is not None:
        if str(body.selected_action).strip().lower() == str(expected_decision).strip().lower():
            return 1.0, "Correct decision.", []
        else:
            return (
                0.0,
                f"Incorrect decision. The expected decision was: {expected_decision}",
                ["decision_mismatch"],
            )

    # Prescription screening: expected_pharmacist_action
    expected_action = payload.get("expected_pharmacist_action")
    if expected_action is not None and body.selected_action is not None:
        if str(body.selected_action).strip().lower() == str(expected_action).strip().lower():
            return 1.0, "Correct pharmacist action.", []
        else:
            return (
                0.0,
                f"Incorrect action. The expected action was: {expected_action}",
                ["action_mismatch"],
            )

    # No structured scoring available for this content type / payload
    return (
        None,
        "Your attempt has been recorded. Automated scoring is not available for this item type.",
        failed,
    )


async def _get_active_publication(
    item_id: uuid.UUID,
    region_code: str,
    db: AsyncSession,
) -> PublicationRecord | None:
    """Return the active PublicationRecord for (item, region), or None."""
    result = await db.execute(
        select(PublicationRecord)
        .where(
            PublicationRecord.content_item_id == item_id,
            PublicationRecord.region_code == region_code,
            PublicationRecord.publication_status == "published",
        )
        .order_by(PublicationRecord.published_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _get_region_rule_flags(
    region_code: str,
    content_type: str,
    db: AsyncSession,
) -> tuple[bool, bool]:
    """Return (requires_local_disclaimer, requires_protocol_note) for a region+type."""
    result = await db.execute(
        select(
            RegionPublishingRule.requires_local_disclaimer,
            RegionPublishingRule.requires_protocol_note,
        )
        .where(
            RegionPublishingRule.region_code == region_code,
            RegionPublishingRule.is_active.is_(True),
            or_(
                RegionPublishingRule.content_type == content_type,
                RegionPublishingRule.content_type.is_(None),
            ),
        )
        .limit(1)
    )
    row = result.one_or_none()
    if row is None:
        return False, False
    return bool(row.requires_local_disclaimer), bool(row.requires_protocol_note)


# ---------------------------------------------------------------------------
# Browse published content
# ---------------------------------------------------------------------------

@router.get("/content", response_model=LearnableContentListResponse)
async def browse_published_content(
    region_code: str = Query(..., description="Region to browse: UK, US, GCC, AU"),
    content_type: Optional[str] = Query(None),
    domain: Optional[str] = Query(None),
    difficulty: Optional[str] = Query(None),
    search: Optional[str] = Query(None, max_length=200),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LearnableContentListResponse:
    """Browse all content published for a given region.

    Returns only items with an active PublicationRecord (status='published').
    Includes the published ContentVersion id and version_number.
    Excludes all admin metadata.
    """
    if region_code not in REGION_CODES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"region_code must be one of {sorted(REGION_CODES)}",
        )
    if content_type and content_type not in CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"content_type must be one of {sorted(CONTENT_TYPES)}",
        )

    # Join ContentItem → PublicationRecord → ContentVersion (the published version)
    q = (
        select(
            ContentItem.id,
            ContentItem.external_id,
            ContentItem.title,
            ContentItem.content_type,
            ContentItem.domain,
            ContentItem.specialty,
            ContentItem.difficulty,
            ContentItem.region_scope,
            PublicationRecord.published_at,
            ContentVersion.id.label("version_id"),
            ContentVersion.version_number,
        )
        .join(PublicationRecord, PublicationRecord.content_item_id == ContentItem.id)
        .join(ContentVersion, ContentVersion.id == PublicationRecord.content_version_id)
        .where(
            PublicationRecord.region_code == region_code,
            PublicationRecord.publication_status == "published",
            ContentItem.status == "published",
        )
        .distinct(ContentItem.id)
    )

    if content_type:
        q = q.where(ContentItem.content_type == content_type)
    if domain:
        q = q.where(ContentItem.domain.ilike(f"%{domain.strip()}%"))
    if difficulty:
        q = q.where(ContentItem.difficulty == difficulty)
    if search:
        term = f"%{search.strip()}%"
        q = q.where(
            or_(
                ContentItem.title.ilike(term),
                ContentItem.external_id.ilike(term),
            )
        )

    count_result = await db.execute(select(func.count()).select_from(q.subquery()))
    total = count_result.scalar_one()
    pages = math.ceil(total / page_size) if total else 1
    offset = (page - 1) * page_size

    rows = (
        await db.execute(
            q.order_by(PublicationRecord.published_at.desc()).offset(offset).limit(page_size)
        )
    ).all()

    items = [
        LearnableContentItem(
            id=r.id,
            external_id=r.external_id,
            title=r.title,
            content_type=r.content_type,
            domain=r.domain,
            specialty=r.specialty,
            difficulty=r.difficulty,
            region_scope=r.region_scope,
            published_at=r.published_at,
            version_id=r.version_id,
            version_number=r.version_number,
        )
        for r in rows
    ]

    return LearnableContentListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


# ---------------------------------------------------------------------------
# Published content detail
# ---------------------------------------------------------------------------

@router.get("/content/{item_id}", response_model=LearnableContentDetail)
async def get_published_content_detail(
    item_id: uuid.UUID,
    region_code: str = Query(..., description="Region to retrieve content for"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LearnableContentDetail:
    """Return the published detail for a content item in a specific region.

    Returns 404 if the item is not published for that region.
    Answer/scoring keys are stripped from the payload.
    """
    if region_code not in REGION_CODES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"region_code must be one of {sorted(REGION_CODES)}",
        )

    # Single join query: item + publication + version
    result = await db.execute(
        select(
            ContentItem.id,
            ContentItem.external_id,
            ContentItem.title,
            ContentItem.content_type,
            ContentItem.domain,
            ContentItem.specialty,
            ContentItem.difficulty,
            ContentItem.region_scope,
            PublicationRecord.published_at,
            ContentVersion.id.label("version_id"),
            ContentVersion.version_number,
            ContentVersion.payload_json,
            ContentVersion.evidence_ids,
            ContentVersion.localization_notes,
        )
        .join(PublicationRecord, PublicationRecord.content_item_id == ContentItem.id)
        .join(ContentVersion, ContentVersion.id == PublicationRecord.content_version_id)
        .where(
            ContentItem.id == item_id,
            PublicationRecord.region_code == region_code,
            PublicationRecord.publication_status == "published",
            ContentItem.status == "published",
        )
        .limit(1)
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content not found or not published for this region.",
        )

    requires_disclaimer, requires_protocol = await _get_region_rule_flags(
        region_code, row.content_type, db
    )

    return LearnableContentDetail(
        id=row.id,
        external_id=row.external_id,
        title=row.title,
        content_type=row.content_type,
        domain=row.domain,
        specialty=row.specialty,
        difficulty=row.difficulty,
        region_scope=row.region_scope,
        published_at=row.published_at,
        version_id=row.version_id,
        version_number=row.version_number,
        safe_payload=_strip_answer_keys(row.payload_json),
        evidence_ids=row.evidence_ids,
        localization_notes=row.localization_notes,
        requires_local_disclaimer=requires_disclaimer,
        requires_protocol_note=requires_protocol,
    )


# ---------------------------------------------------------------------------
# Submit attempt
# ---------------------------------------------------------------------------

@router.post(
    "/content/{item_id}/attempt",
    response_model=LearnerAttemptResult,
    status_code=status.HTTP_201_CREATED,
)
async def submit_attempt(
    item_id: uuid.UUID,
    body: LearnerAttemptCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LearnerAttemptResult:
    """Submit a learner attempt against a published content item.

    Validates item is published for body.region_code.
    Scores deterministically against structured payload fields if available.
    Creates a LearnerFailureAnalytics record.
    Does not use AI. Does not invent clinical feedback.
    """
    if body.region_code not in REGION_CODES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"region_code must be one of {sorted(REGION_CODES)}",
        )

    # Verify published
    result = await db.execute(
        select(
            ContentItem.id,
            ContentItem.content_type,
            PublicationRecord.content_version_id,
            ContentVersion.payload_json,
        )
        .join(PublicationRecord, PublicationRecord.content_item_id == ContentItem.id)
        .join(ContentVersion, ContentVersion.id == PublicationRecord.content_version_id)
        .where(
            ContentItem.id == item_id,
            PublicationRecord.region_code == body.region_code,
            PublicationRecord.publication_status == "published",
            ContentItem.status == "published",
        )
        .limit(1)
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content not found or not published for this region.",
        )

    content_type = row.content_type
    payload = row.payload_json
    version_id = row.content_version_id

    # Deterministic scoring
    score, feedback, failed_dims = _score_attempt(content_type, payload, body)

    # Map learner flags to failure dimensions
    failed_red_flag = body.red_flag_identified is False
    failed_counseling = body.counseling_point_selected is False
    failed_interaction = body.interaction_detected is False
    failed_referral = body.referral_decision_selected is False
    failed_dose = body.dose_calculation_answer is not None and not body.dose_calculation_answer.strip()
    failed_documentation = body.documentation_completed is False

    analytics = LearnerFailureAnalytics(
        content_item_id=item_id,
        content_version_id=version_id,
        user_id=current_user.id,
        region_code=body.region_code,
        attempt_type=body.attempt_type,
        score=score,
        failed_red_flag=failed_red_flag,
        failed_counseling_point=failed_counseling,
        failed_interaction_detection=failed_interaction,
        failed_referral_decision=failed_referral,
        failed_dose_calculation=failed_dose,
        failed_documentation=failed_documentation,
        time_to_decision_seconds=body.time_to_decision_seconds,
    )
    db.add(analytics)
    await db.commit()
    await db.refresh(analytics)

    # Build failed_dimensions list for the response
    all_failed: list[str] = list(failed_dims)
    if failed_red_flag:
        all_failed.append("red_flag")
    if failed_counseling:
        all_failed.append("counseling_point")
    if failed_interaction:
        all_failed.append("interaction_detection")
    if failed_referral:
        all_failed.append("referral_decision")
    if failed_dose:
        all_failed.append("dose_calculation")
    if failed_documentation:
        all_failed.append("documentation")

    # Recommended next step
    if score is not None and score >= 1.0:
        next_step = "Well done — try the next item in this domain."
    elif score == 0.0:
        next_step = "Review the content and retry."
    elif all_failed:
        next_step = f"Focus on: {', '.join(all_failed[:2])}."
    else:
        next_step = "Continue practising similar items to build confidence."

    return LearnerAttemptResult(
        attempt_id=analytics.id,
        score=score,
        feedback=feedback,
        failed_dimensions=all_failed,
        recommended_next_step=next_step,
    )


# ---------------------------------------------------------------------------
# Learner progress
# ---------------------------------------------------------------------------

@router.get("/progress", response_model=LearnerProgressSummary)
async def get_learner_progress(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LearnerProgressSummary:
    """Return progress summary for the current learner.

    Aggregates from LearnerFailureAnalytics scoped to current_user.id only.
    """
    user_id = current_user.id

    # Totals
    totals = (await db.execute(
        select(
            func.count(LearnerFailureAnalytics.id).label("total"),
            func.avg(LearnerFailureAnalytics.score).label("avg_score"),
        )
        .where(LearnerFailureAnalytics.user_id == user_id)
    )).one()

    total_attempts = totals.total or 0
    average_score = round(float(totals.avg_score), 3) if totals.avg_score is not None else None

    # By content type
    type_rows = (await db.execute(
        select(
            ContentItem.content_type,
            func.count(LearnerFailureAnalytics.id).label("n"),
        )
        .join(ContentItem, ContentItem.id == LearnerFailureAnalytics.content_item_id)
        .where(LearnerFailureAnalytics.user_id == user_id)
        .group_by(ContentItem.content_type)
    )).all()
    attempts_by_content_type = {r.content_type: r.n for r in type_rows}

    # Weakness breakdown: dimension → fail rate (only over attempts with those flags explicitly set)
    dim_row = (await db.execute(
        select(
            func.count(LearnerFailureAnalytics.id).label("total"),
            func.sum(cast(LearnerFailureAnalytics.failed_red_flag, Integer)).label("red_flag"),
            func.sum(cast(LearnerFailureAnalytics.failed_counseling_point, Integer)).label("counseling"),
            func.sum(cast(LearnerFailureAnalytics.failed_interaction_detection, Integer)).label("interaction"),
            func.sum(cast(LearnerFailureAnalytics.failed_referral_decision, Integer)).label("referral"),
            func.sum(cast(LearnerFailureAnalytics.failed_dose_calculation, Integer)).label("dose_calc"),
            func.sum(cast(LearnerFailureAnalytics.failed_documentation, Integer)).label("documentation"),
        )
        .where(LearnerFailureAnalytics.user_id == user_id)
    )).one()

    weakness: dict[str, float] = {}
    if dim_row.total:
        for key, col in [
            ("red_flag", dim_row.red_flag),
            ("counseling_point", dim_row.counseling),
            ("interaction_detection", dim_row.interaction),
            ("referral_decision", dim_row.referral),
            ("dose_calculation", dim_row.dose_calc),
            ("documentation", dim_row.documentation),
        ]:
            weakness[key] = round(float(col or 0) / dim_row.total, 3)

    # Recent attempts (last 10)
    recent_rows = (await db.execute(
        select(
            LearnerFailureAnalytics.id,
            LearnerFailureAnalytics.content_item_id,
            LearnerFailureAnalytics.region_code,
            LearnerFailureAnalytics.score,
            LearnerFailureAnalytics.attempt_type,
            LearnerFailureAnalytics.created_at,
            ContentItem.title.label("content_title"),
            ContentItem.content_type,
        )
        .join(ContentItem, ContentItem.id == LearnerFailureAnalytics.content_item_id)
        .where(LearnerFailureAnalytics.user_id == user_id)
        .order_by(LearnerFailureAnalytics.created_at.desc())
        .limit(10)
    )).all()

    recent = [
        LearnerRecentAttempt(
            id=r.id,
            content_item_id=r.content_item_id,
            content_title=r.content_title,
            content_type=r.content_type,
            region_code=r.region_code,
            score=r.score,
            attempt_type=r.attempt_type,
            created_at=r.created_at,
        )
        for r in recent_rows
    ]

    return LearnerProgressSummary(
        total_attempts=total_attempts,
        average_score=average_score,
        attempts_by_content_type=attempts_by_content_type,
        weakness_breakdown=weakness,
        recent_attempts=recent,
    )

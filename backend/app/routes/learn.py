"""Learner-facing published content routes.

Security contract:
- Only content with an active PublicationRecord (status='published') is returned.
- Answer/scoring keys are stripped from all pre-submission responses.
- Reveal keys appear only in session submit responses, never before.
- Session records are scoped to current_user.id — no cross-user access.
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
    LearnerTrainingSession,
    PublicationRecord,
    RegionPublishingRule,
)
from app.models.identity import User
from app.schemas.learn import (
    DimensionFeedbackItem,
    LearnableContentDetail,
    LearnableContentItem,
    LearnableContentListResponse,
    LearnerAttemptCreate,
    LearnerAttemptResult,
    LearnerProgressSummary,
    LearnerRecentAttempt,
    LearnerSessionSummary,
    SessionStartRequest,
    SessionStartResponse,
    SessionSubmitRequest,
    SessionSubmitResponse,
    TrainingFlowResponse,
    TrainingFlowStep,
)
from app.services.entitlements import can_start_training_session, record_usage_event
from app.services.training_engine import REVEAL_KEYS, build_training_flow, score_submission

router = APIRouter(prefix="/api/learn", tags=["learner"])

# Single source of truth for answer/scoring keys that must never be returned
# to learners before submission. Imported from training_engine to prevent drift.
_ANSWER_KEYS = REVEAL_KEYS


def _strip_answer_keys(payload: dict | None) -> dict | None:
    if not payload:
        return payload
    return {k: v for k, v in payload.items() if k not in _ANSWER_KEYS}


def _score_attempt(
    content_type: str,
    payload: dict | None,
    body: LearnerAttemptCreate,
) -> tuple[float | None, str, list[str]]:
    """Phase-1 deterministic scoring. Kept for the /attempt endpoint."""
    if not payload:
        return None, "Your attempt has been recorded. Feedback requires supervisor review.", []

    correct = payload.get("correct_answer_or_expected_response")
    if correct is not None and body.learner_response is not None:
        if str(body.learner_response).strip().lower() == str(correct).strip().lower():
            return 1.0, "Correct! Your answer matches the expected response.", []
        return 0.0, f"Incorrect. The expected response was: {correct}", ["response_mismatch"]

    expected_decision = payload.get("expected_decision")
    if expected_decision is not None and body.selected_action is not None:
        if str(body.selected_action).strip().lower() == str(expected_decision).strip().lower():
            return 1.0, "Correct decision.", []
        return 0.0, f"Incorrect decision. Expected: {expected_decision}", ["decision_mismatch"]

    expected_action = payload.get("expected_pharmacist_action")
    if expected_action is not None and body.selected_action is not None:
        if str(body.selected_action).strip().lower() == str(expected_action).strip().lower():
            return 1.0, "Correct pharmacist action.", []
        return 0.0, f"Incorrect action. Expected: {expected_action}", ["action_mismatch"]

    return (
        None,
        "Your attempt has been recorded. Automated scoring is not available for this item type.",
        [],
    )


async def _get_active_publication(
    item_id: uuid.UUID,
    region_code: str,
    db: AsyncSession,
) -> PublicationRecord | None:
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


async def _fetch_published_row(
    item_id: uuid.UUID,
    region_code: str,
    db: AsyncSession,
):
    """Single join for published item + version. Returns row or None."""
    result = await db.execute(
        select(
            ContentItem.id,
            ContentItem.content_type,
            ContentItem.title,
            PublicationRecord.content_version_id,
            ContentVersion.payload_json,
            ContentVersion.version_number,
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
    return result.one_or_none()


# ---------------------------------------------------------------------------
# Browse published content
# ---------------------------------------------------------------------------

@router.get("/content", response_model=LearnableContentListResponse)
async def browse_published_content(
    region_code: str = Query(..., description="Region: UK, US, GCC, AU"),
    content_type: Optional[str] = Query(None),
    domain: Optional[str] = Query(None),
    difficulty: Optional[str] = Query(None),
    search: Optional[str] = Query(None, max_length=200),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LearnableContentListResponse:
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
            or_(ContentItem.title.ilike(term), ContentItem.external_id.ilike(term))
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

    return LearnableContentListResponse(
        items=[
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
        ],
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
    region_code: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LearnableContentDetail:
    if region_code not in REGION_CODES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"region_code must be one of {sorted(REGION_CODES)}",
        )

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
        raise HTTPException(status_code=404, detail="Content not found or not published for this region.")

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
# Training flow (pre-submission step blueprint)
# ---------------------------------------------------------------------------

@router.get("/content/{item_id}/training-flow", response_model=TrainingFlowResponse)
async def get_training_flow(
    item_id: uuid.UUID,
    region_code: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TrainingFlowResponse:
    """Return the structured training flow for a published content item.

    Hidden fields (answer keys, rubrics, risk info) are NEVER included.
    Reveal fields appear only in the session submit response.
    """
    if region_code not in REGION_CODES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"region_code must be one of {sorted(REGION_CODES)}",
        )

    row = await _fetch_published_row(item_id, region_code, db)
    if row is None:
        raise HTTPException(status_code=404, detail="Content not found or not published for this region.")

    payload = row.payload_json or {}
    steps_data = build_training_flow(row.content_type, payload)

    # Build scoring note based on content type
    if row.content_type in ("case", "prescription_screening", "drill"):
        scoring_note = "Automated scoring available for your primary decision."
    else:
        scoring_note = (
            "Guided training available; automated scoring is limited for this content type."
        )

    steps = [TrainingFlowStep(**s) for s in steps_data]

    return TrainingFlowResponse(
        content_item_id=item_id,
        content_type=row.content_type,
        title=row.title,
        total_steps=len(steps),
        steps=steps,
        scoring_note=scoring_note,
    )


# ---------------------------------------------------------------------------
# Start training session
# ---------------------------------------------------------------------------

@router.post(
    "/content/{item_id}/sessions",
    response_model=SessionStartResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_training_session(
    item_id: uuid.UUID,
    body: SessionStartRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SessionStartResponse:
    """Create a new training session for a published content item.

    Verifies the item is published for the requested region.
    Uses the currently published version.
    Does not expose hidden fields.
    """
    if body.region_code not in REGION_CODES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"region_code must be one of {sorted(REGION_CODES)}",
        )

    # Entitlement check — platform admins bypass all limits
    allowed, reason = await can_start_training_session(
        db, current_user.id, is_superuser=current_user.is_superuser
    )
    if not allowed:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=reason)

    row = await _fetch_published_row(item_id, body.region_code, db)
    if row is None:
        raise HTTPException(status_code=404, detail="Content not found or not published for this region.")

    payload = row.payload_json or {}
    steps_data = build_training_flow(row.content_type, payload)
    total_steps = len(steps_data)

    session = LearnerTrainingSession(
        user_id=current_user.id,
        content_item_id=item_id,
        content_version_id=row.content_version_id,
        region_code=body.region_code,
        status="started",
        current_step=1,
        total_steps=total_steps,
        started_at=datetime.now(timezone.utc),
    )
    db.add(session)

    await record_usage_event(
        db,
        current_user.id,
        "training_session_started",
        content_item_id=item_id,
        content_version_id=row.content_version_id,
    )

    await db.commit()
    await db.refresh(session)

    return SessionStartResponse(
        session_id=session.id,
        content_item_id=session.content_item_id,
        content_version_id=session.content_version_id,
        region_code=session.region_code,
        status=session.status,
        current_step=session.current_step,
        total_steps=session.total_steps,
        started_at=session.started_at,
    )


# ---------------------------------------------------------------------------
# Submit training session
# ---------------------------------------------------------------------------

@router.post("/sessions/{session_id}/submit", response_model=SessionSubmitResponse)
async def submit_training_session(
    session_id: uuid.UUID,
    body: SessionSubmitRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SessionSubmitResponse:
    """Submit a completed training session.

    - Verifies session belongs to current_user.
    - Verifies session is not already completed.
    - Scores deterministically from structured payload fields only.
    - Creates LearnerFailureAnalytics record.
    - Returns reveal_summary with post-submission payload fields.
    """
    # Load session
    sess_result = await db.execute(
        select(LearnerTrainingSession).where(LearnerTrainingSession.id == session_id)
    )
    session = sess_result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorised to submit this session.")
    if session.status == "completed":
        raise HTTPException(status_code=409, detail="Session already completed.")

    # Load content version payload
    version_result = await db.execute(
        select(ContentVersion.payload_json, ContentItem.content_type)
        .join(ContentItem, ContentItem.id == ContentVersion.content_item_id)
        .where(ContentVersion.id == session.content_version_id)
    )
    version_row = version_result.one_or_none()
    if version_row is None:
        raise HTTPException(status_code=404, detail="Content version not found.")

    payload = version_row.payload_json or {}
    content_type = version_row.content_type

    # Score deterministically
    scoring = score_submission(
        content_type,
        payload,
        action_selected=body.action_selected,
        answer_text=body.answer_text,
        red_flags_selected=body.red_flags_selected,
        counseling_points=body.counseling_points,
        documentation_points=body.documentation_points,
        confidence=body.confidence,
        time_to_decision_seconds=body.time_to_decision_seconds,
    )

    now = datetime.now(timezone.utc)

    # Update session
    session.status = "completed"
    session.completed_at = now
    session.current_step = session.total_steps
    session.score = scoring.score
    session.max_score = scoring.max_score
    session.score_percent = scoring.score_percent
    session.failed_dimensions_json = scoring.failed_dimensions
    session.not_assessable_dimensions_json = scoring.not_assessable_dimensions
    session.learner_responses_json = {
        "action_selected": body.action_selected,
        "answer_text": body.answer_text,
        "red_flags_selected": body.red_flags_selected,
        "counseling_points": body.counseling_points,
        "documentation_points": body.documentation_points,
        "confidence": body.confidence,
        "time_to_decision_seconds": body.time_to_decision_seconds,
    }
    session.feedback_json = [
        {"dimension": r.dimension, "status": r.status, "feedback": r.feedback}
        for r in scoring.dimension_results
    ]

    # Create LearnerFailureAnalytics record
    failed_dims = set(scoring.failed_dimensions)
    analytics = LearnerFailureAnalytics(
        content_item_id=session.content_item_id,
        content_version_id=session.content_version_id,
        user_id=current_user.id,
        region_code=session.region_code,
        attempt_type="session",
        score=scoring.score,
        failed_red_flag="red_flag_recognition" in failed_dims,
        failed_counseling_point="counseling_quality" in failed_dims,
        failed_interaction_detection="interaction_detection" in failed_dims,
        failed_referral_decision="triage_or_referral_decision" in failed_dims,
        failed_dose_calculation="calculation_accuracy" in failed_dims,
        failed_documentation="documentation_quality" in failed_dims,
        time_to_decision_seconds=body.time_to_decision_seconds,
    )
    db.add(analytics)

    await record_usage_event(
        db,
        current_user.id,
        "training_session_completed",
        content_item_id=session.content_item_id,
        content_version_id=session.content_version_id,
    )

    await db.commit()
    await db.refresh(session)

    return SessionSubmitResponse(
        session_id=session.id,
        status=session.status,
        score=session.score,
        max_score=session.max_score,
        score_percent=session.score_percent,
        failed_dimensions=session.failed_dimensions_json or [],
        not_assessable_dimensions=session.not_assessable_dimensions_json or [],
        dimension_feedback=[
            DimensionFeedbackItem(
                dimension=r.dimension,
                status=r.status,
                feedback=r.feedback,
            )
            for r in scoring.dimension_results
        ],
        reveal_summary=scoring.reveal_summary,
        next_recommendation=scoring.next_recommendation,
    )


# ---------------------------------------------------------------------------
# Submit attempt (Phase 1 — kept for backwards compatibility)
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
    if body.region_code not in REGION_CODES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"region_code must be one of {sorted(REGION_CODES)}",
        )

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
        raise HTTPException(status_code=404, detail="Content not found or not published for this region.")

    score, feedback, failed_dims = _score_attempt(row.content_type, row.payload_json, body)

    failed_red_flag = body.red_flag_identified is False
    failed_counseling = body.counseling_point_selected is False
    failed_interaction = body.interaction_detected is False
    failed_referral = body.referral_decision_selected is False
    failed_dose = body.dose_calculation_answer is not None and not body.dose_calculation_answer.strip()
    failed_documentation = body.documentation_completed is False

    analytics = LearnerFailureAnalytics(
        content_item_id=item_id,
        content_version_id=row.content_version_id,
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
    """Return comprehensive progress summary for the current learner.

    Aggregates from both LearnerFailureAnalytics and LearnerTrainingSession,
    scoped exclusively to current_user.id.
    """
    user_id = current_user.id

    # ── Analytics totals ───────────────────────────────────────────────────
    totals = (await db.execute(
        select(
            func.count(LearnerFailureAnalytics.id).label("total"),
            func.avg(LearnerFailureAnalytics.score).label("avg_score"),
        )
        .where(LearnerFailureAnalytics.user_id == user_id)
    )).one()

    total_attempts = totals.total or 0
    average_score = round(float(totals.avg_score), 3) if totals.avg_score is not None else None

    # ── Session totals ─────────────────────────────────────────────────────
    session_totals = (await db.execute(
        select(
            func.count(LearnerTrainingSession.id).label("total"),
            func.avg(LearnerTrainingSession.score_percent).label("avg_pct"),
        )
        .where(
            LearnerTrainingSession.user_id == user_id,
            LearnerTrainingSession.status == "completed",
        )
    )).one()

    completed_sessions = session_totals.total or 0
    average_score_percent = (
        round(float(session_totals.avg_pct), 1)
        if session_totals.avg_pct is not None
        else None
    )

    # ── By content type ────────────────────────────────────────────────────
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

    # ── Dimension breakdown ────────────────────────────────────────────────
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

    dimension_breakdown: dict[str, float] = {}
    if dim_row.total:
        for key, col in [
            ("red_flag_recognition", dim_row.red_flag),
            ("counseling_quality", dim_row.counseling),
            ("interaction_detection", dim_row.interaction),
            ("triage_or_referral_decision", dim_row.referral),
            ("calculation_accuracy", dim_row.dose_calc),
            ("documentation_quality", dim_row.documentation),
        ]:
            dimension_breakdown[key] = round(float(col or 0) / dim_row.total, 3)

    # Keep old weakness_breakdown field name for compatibility
    weakness_breakdown = dimension_breakdown

    # ── Strongest / weakest dimension ─────────────────────────────────────
    weakest_dimension: Optional[str] = None
    strongest_dimension: Optional[str] = None
    if dimension_breakdown:
        dims_with_failures = {k: v for k, v in dimension_breakdown.items() if v > 0}
        if dims_with_failures:
            weakest_dimension = max(dims_with_failures, key=lambda k: dims_with_failures[k])
        # Strongest = lowest fail rate across all tracked dimensions (always shown if data exists)
        strongest_dimension = min(dimension_breakdown, key=lambda k: dimension_breakdown[k])

    # ── Recommended next ───────────────────────────────────────────────────
    recommended_next_content_type: Optional[str] = None
    recommended_next_domain: Optional[str] = None

    _DIM_TO_TYPE: dict[str, str] = {
        "triage_or_referral_decision": "case",
        "red_flag_recognition": "case",
        "calculation_accuracy": "drill",
        "counseling_quality": "simulation",
        "documentation_quality": "simulation",
        "communication_safety": "simulation",
        "medication_safety": "prescription_screening",
        "interaction_detection": "prescription_screening",
    }
    if weakest_dimension:
        recommended_next_content_type = _DIM_TO_TYPE.get(weakest_dimension)

    # Recommend domain from weakest recent session
    if completed_sessions > 0:
        recent_domain_row = (await db.execute(
            select(ContentItem.domain)
            .join(LearnerTrainingSession, LearnerTrainingSession.content_item_id == ContentItem.id)
            .where(
                LearnerTrainingSession.user_id == user_id,
                LearnerTrainingSession.status == "completed",
                LearnerTrainingSession.score_percent.isnot(None),
                LearnerTrainingSession.score_percent < 60,
            )
            .order_by(LearnerTrainingSession.completed_at.desc())
            .limit(1)
        )).one_or_none()
        if recent_domain_row and recent_domain_row.domain:
            recommended_next_domain = recent_domain_row.domain

    # ── Recent attempts ────────────────────────────────────────────────────
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

    recent_attempts = [
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

    # ── Recent sessions ────────────────────────────────────────────────────
    recent_session_rows = (await db.execute(
        select(
            LearnerTrainingSession.id,
            LearnerTrainingSession.content_item_id,
            LearnerTrainingSession.region_code,
            LearnerTrainingSession.status,
            LearnerTrainingSession.score,
            LearnerTrainingSession.score_percent,
            LearnerTrainingSession.started_at,
            LearnerTrainingSession.completed_at,
            ContentItem.title.label("content_title"),
            ContentItem.content_type,
        )
        .join(ContentItem, ContentItem.id == LearnerTrainingSession.content_item_id)
        .where(LearnerTrainingSession.user_id == user_id)
        .order_by(LearnerTrainingSession.started_at.desc())
        .limit(10)
    )).all()

    recent_sessions = [
        LearnerSessionSummary(
            id=r.id,
            content_item_id=r.content_item_id,
            content_title=r.content_title,
            content_type=r.content_type,
            region_code=r.region_code,
            status=r.status,
            score=r.score,
            score_percent=r.score_percent,
            started_at=r.started_at,
            completed_at=r.completed_at,
        )
        for r in recent_session_rows
    ]

    return LearnerProgressSummary(
        total_attempts=total_attempts,
        completed_sessions=completed_sessions,
        average_score=average_score,
        average_score_percent=average_score_percent,
        strongest_dimension=strongest_dimension,
        weakest_dimension=weakest_dimension,
        attempts_by_content_type=attempts_by_content_type,
        dimension_breakdown=dimension_breakdown,
        weakness_breakdown=weakness_breakdown,
        recent_attempts=recent_attempts,
        recent_sessions=recent_sessions,
        recommended_next_content_type=recommended_next_content_type,
        recommended_next_domain=recommended_next_domain,
    )

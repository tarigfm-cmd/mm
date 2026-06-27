"""Evidence source routes."""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, require_content_permission
from app.database import get_db
from app.models.governance import EvidenceSource
from app.models.identity import User
from app.schemas.governance import (
    EvidenceSourceCreate,
    EvidenceSourceRead,
    EvidenceSourceUpdate,
)
from app.services.audit import log_action

router = APIRouter(prefix="/api/evidence", tags=["evidence"])


@router.post("/sources", response_model=EvidenceSourceRead, status_code=status.HTTP_201_CREATED)
async def create_evidence_source(
    body: EvidenceSourceCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_permission("evidence.manage")),
):
    source = EvidenceSource(**body.model_dump())
    db.add(source)
    await db.flush()
    await log_action(
        db,
        action="content.evidence_source_created",
        actor_user_id=current_user.id,
        resource_type="evidence_source",
        resource_id=str(source.id),
        details={"title": source.title},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(source)
    return source


@router.get("/sources", response_model=list[EvidenceSourceRead])
async def list_evidence_sources(
    region: Optional[str] = Query(None),
    evidence_status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(EvidenceSource)
    if region:
        q = q.where(EvidenceSource.region == region)
    if evidence_status:
        q = q.where(EvidenceSource.evidence_status == evidence_status)
    result = await db.execute(q.order_by(EvidenceSource.title.asc()))
    return result.scalars().all()


@router.patch("/sources/{source_id}", response_model=EvidenceSourceRead)
async def update_evidence_source(
    source_id: uuid.UUID,
    body: EvidenceSourceUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_permission("evidence.manage")),
):
    source = await db.get(EvidenceSource, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Evidence source not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(source, field, value)
    source.updated_at = datetime.now(timezone.utc)

    await log_action(
        db,
        action="content.evidence_source_updated",
        actor_user_id=current_user.id,
        resource_type="evidence_source",
        resource_id=str(source_id),
        details={"updated_fields": list(update_data.keys())},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(source)
    return source


@router.get("/due-for-review", response_model=list[EvidenceSourceRead])
async def list_due_for_review(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_permission("evidence.manage")),
):
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(EvidenceSource)
        .where(
            EvidenceSource.next_review_due_at != None,  # noqa: E711
            EvidenceSource.next_review_due_at <= now,
            EvidenceSource.evidence_status != "retired",
        )
        .order_by(EvidenceSource.next_review_due_at.asc())
    )
    return result.scalars().all()

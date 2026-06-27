"""Content governance routes: items, versions, reviews, publishing, batches."""
import hashlib
import math
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import (
    get_current_user,
    has_permission,
    require_content_permission,
    require_superuser,
)
from app.database import get_db
from app.models.governance import (
    CONTENT_TYPES,
    CONTENT_STATUSES,
    REGION_CODES,
    ApprovalBatch,
    ClinicalReview,
    ContentItem,
    ContentVersion,
    EvidenceSource,
    PublicationRecord,
    RegionPublishingRule,
)
from app.models.identity import User
from app.schemas.governance import (
    ApprovalBatchCreate,
    ApprovalBatchRead,
    ClinicalReviewCreate,
    ClinicalReviewRead,
    ContentItemCreate,
    ContentItemListItem,
    ContentItemListResponse,
    ContentItemRead,
    ContentVersionCreate,
    ContentVersionRead,
    PublicationRecordRead,
    PublishRequest,
    UnpublishRequest,
)
from app.services.audit import log_action

router = APIRouter(prefix="/api/content", tags=["content-governance"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _payload_hash(payload: dict | None) -> str | None:
    if payload is None:
        return None
    raw = str(sorted(payload.items())).encode()
    return hashlib.sha256(raw).hexdigest()


async def _get_item_or_404(item_id: uuid.UUID, db: AsyncSession) -> ContentItem:
    row = await db.get(ContentItem, item_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Content item not found")
    return row


async def _enforce_region_rules(
    item: ContentItem,
    region_code: str,
    current_version: Optional[ContentVersion],
    db: AsyncSession,
) -> None:
    """Block publish if an active RegionPublishingRule is violated."""
    rule_result = await db.execute(
        select(RegionPublishingRule).where(
            RegionPublishingRule.region_code == region_code,
            RegionPublishingRule.is_active.is_(True),
            or_(
                RegionPublishingRule.content_type.is_(None),
                RegionPublishingRule.content_type == item.content_type,
            ),
        ).limit(1)
    )
    rule = rule_result.scalars().first()
    if rule is None:
        return

    # Check allowed statuses
    if rule.allowed_statuses and item.status not in rule.allowed_statuses:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Region rule for {region_code} requires item status in "
                f"{rule.allowed_statuses}; current status is '{item.status}'"
            ),
        )

    # Check required evidence region (only if version has evidence_ids)
    if rule.required_evidence_region and current_version and current_version.evidence_ids:
        try:
            evidence_uuids = [uuid.UUID(eid) for eid in current_version.evidence_ids]
        except (ValueError, TypeError):
            evidence_uuids = []

        if evidence_uuids:
            count = await db.scalar(
                select(func.count(EvidenceSource.id)).where(
                    EvidenceSource.id.in_(evidence_uuids),
                    EvidenceSource.region == rule.required_evidence_region,
                    EvidenceSource.evidence_status.notin_(["retired", "superseded"]),
                )
            )
            if (count or 0) == 0:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Region rule for {region_code} requires at least one active "
                        f"evidence source from region '{rule.required_evidence_region}'"
                    ),
                )


# ---------------------------------------------------------------------------
# Approval Batches
# ---------------------------------------------------------------------------


@router.post(
    "/approval-batches",
    response_model=ApprovalBatchRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_approval_batch(
    body: ApprovalBatchCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_permission("content.approve")),
):
    batch = ApprovalBatch(
        **body.model_dump(),
        approved_by_user_id=current_user.id,
    )
    db.add(batch)
    await db.flush()
    await log_action(
        db,
        action="content.approval_batch_created",
        actor_user_id=current_user.id,
        resource_type="approval_batch",
        resource_id=str(batch.id),
        details={"batch_name": batch.batch_name},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(batch)
    return batch


@router.get("/approval-batches", response_model=list[ApprovalBatchRead])
async def list_approval_batches(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_permission("content.review")),
):
    result = await db.execute(
        select(ApprovalBatch).order_by(ApprovalBatch.approved_at.desc())
    )
    return result.scalars().all()


# ---------------------------------------------------------------------------
# Content Items
# ---------------------------------------------------------------------------


@router.post("/items", response_model=ContentItemRead, status_code=status.HTTP_201_CREATED)
async def create_content_item(
    body: ContentItemCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_permission("content.import")),
):
    item = ContentItem(
        **body.model_dump(),
        status="draft",
        created_by=current_user.id,
    )
    db.add(item)
    await db.flush()
    await log_action(
        db,
        action="content.item_created",
        actor_user_id=current_user.id,
        resource_type="content_item",
        resource_id=str(item.id),
        details={"title": item.title, "content_type": item.content_type},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(item)
    return item


@router.get("/items", response_model=ContentItemListResponse)
async def list_content_items(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    content_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    domain: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(ContentItem)

    # Learners can only see published content; admins can filter by any status
    if not current_user.is_superuser:
        q = q.where(ContentItem.status == "published")
    elif status:
        if status not in CONTENT_STATUSES:
            raise HTTPException(status_code=422, detail=f"Invalid status: {status}")
        q = q.where(ContentItem.status == status)

    if content_type:
        if content_type not in CONTENT_TYPES:
            raise HTTPException(status_code=422, detail=f"Invalid content_type: {content_type}")
        q = q.where(ContentItem.content_type == content_type)
    if domain:
        q = q.where(ContentItem.domain == domain)

    count_result = await db.execute(select(func.count()).select_from(q.subquery()))
    total = count_result.scalar_one()
    pages = math.ceil(total / per_page) if per_page else 1
    offset = (page - 1) * per_page
    rows = (
        await db.execute(
            q.order_by(ContentItem.created_at.desc()).offset(offset).limit(per_page)
        )
    ).scalars().all()

    return ContentItemListResponse(
        items=[ContentItemListItem.model_validate(r) for r in rows],
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
    )


@router.get("/items/{item_id}", response_model=ContentItemRead)
async def get_content_item(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = await _get_item_or_404(item_id, db)
    if not current_user.is_superuser and item.status != "published":
        raise HTTPException(status_code=403, detail="Content is not published")
    return item


# ---------------------------------------------------------------------------
# Content Versions
# ---------------------------------------------------------------------------


@router.get("/items/{item_id}/versions", response_model=list[ContentVersionRead])
async def list_versions(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_permission("content.review")),
):
    await _get_item_or_404(item_id, db)
    result = await db.execute(
        select(ContentVersion)
        .where(ContentVersion.content_item_id == item_id)
        .order_by(ContentVersion.version_number.asc())
    )
    return result.scalars().all()


@router.post(
    "/items/{item_id}/versions",
    response_model=ContentVersionRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_version(
    item_id: uuid.UUID,
    body: ContentVersionCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_permission("content.version.create")),
):
    item = await _get_item_or_404(item_id, db)

    if item.status == "retired":
        raise HTTPException(status_code=409, detail="Cannot add versions to a retired content item")

    count_result = await db.execute(
        select(func.count(ContentVersion.id)).where(ContentVersion.content_item_id == item_id)
    )
    next_number = (count_result.scalar_one() or 0) + 1

    await db.execute(
        update(ContentVersion)
        .where(ContentVersion.content_item_id == item_id)
        .values(is_current=False)
    )

    version = ContentVersion(
        content_item_id=item_id,
        version_number=next_number,
        payload_json=body.payload_json,
        evidence_ids=body.evidence_ids,
        localization_notes=body.localization_notes,
        change_summary=body.change_summary,
        source_file_name=body.source_file_name,
        source_row_number=body.source_row_number,
        created_by=current_user.id,
        is_current=True,
        content_hash=_payload_hash(body.payload_json),
    )
    db.add(version)
    await db.flush()

    item.current_version_id = version.id
    # Track status lifecycle: published → needs_update; draft → pending_review
    if item.status == "published":
        item.status = "needs_update"
    elif item.status in ("draft", "imported"):
        item.status = "pending_review"
    item.updated_at = datetime.now(timezone.utc)

    await log_action(
        db,
        action="content.version_created",
        actor_user_id=current_user.id,
        resource_type="content_version",
        resource_id=str(version.id),
        details={"content_item_id": str(item_id), "version_number": next_number},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(version)
    return version


@router.post(
    "/items/{item_id}/versions/rollback/{version_id}",
    response_model=ContentVersionRead,
    status_code=status.HTTP_201_CREATED,
)
async def rollback_version(
    item_id: uuid.UUID,
    version_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_permission("content.rollback")),
):
    item = await _get_item_or_404(item_id, db)

    if item.status == "retired":
        raise HTTPException(status_code=409, detail="Cannot rollback a retired content item")

    target = await db.get(ContentVersion, version_id)
    if target is None or target.content_item_id != item_id:
        raise HTTPException(status_code=404, detail="Version not found for this item")

    await db.execute(
        update(ContentVersion)
        .where(ContentVersion.content_item_id == item_id)
        .values(is_current=False)
    )

    count_result = await db.execute(
        select(func.count(ContentVersion.id)).where(ContentVersion.content_item_id == item_id)
    )
    next_number = (count_result.scalar_one() or 0) + 1

    rollback_ver = ContentVersion(
        content_item_id=item_id,
        version_number=next_number,
        payload_json=target.payload_json,
        evidence_ids=target.evidence_ids,
        localization_notes=target.localization_notes,
        change_summary=f"Rollback to version {target.version_number}",
        created_by=current_user.id,
        is_current=True,
        content_hash=target.content_hash,
    )
    db.add(rollback_ver)
    await db.flush()

    item.current_version_id = rollback_ver.id
    # Rollback always requires re-review; if published signal needs_update
    if item.status in ("published", "needs_update"):
        item.status = "needs_update"
    else:
        item.status = "pending_review"
    item.updated_at = datetime.now(timezone.utc)

    await log_action(
        db,
        action="content.version_rollback",
        actor_user_id=current_user.id,
        resource_type="content_version",
        resource_id=str(rollback_ver.id),
        details={
            "content_item_id": str(item_id),
            "rollback_to_version_id": str(version_id),
            "rollback_to_version_number": target.version_number,
        },
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(rollback_ver)
    return rollback_ver


# ---------------------------------------------------------------------------
# Clinical Reviews
# ---------------------------------------------------------------------------


@router.post(
    "/items/{item_id}/reviews",
    response_model=ClinicalReviewRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_review(
    item_id: uuid.UUID,
    body: ClinicalReviewCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_permission("content.review")),
):
    await _get_item_or_404(item_id, db)

    # If a specific version is referenced, it must belong to this item
    if body.content_version_id is not None:
        version = await db.get(ContentVersion, body.content_version_id)
        if version is None or version.content_item_id != item_id:
            raise HTTPException(
                status_code=422,
                detail="content_version_id does not belong to this content item",
            )

    review = ClinicalReview(
        content_item_id=item_id,
        reviewer_user_id=current_user.id,
        **body.model_dump(),
    )
    db.add(review)
    await db.flush()

    await log_action(
        db,
        action="content.review_created",
        actor_user_id=current_user.id,
        resource_type="clinical_review",
        resource_id=str(review.id),
        details={
            "content_item_id": str(item_id),
            "review_decision": review.review_decision,
        },
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(review)
    return review


@router.get("/items/{item_id}/reviews", response_model=list[ClinicalReviewRead])
async def list_reviews(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_permission("content.review")),
):
    await _get_item_or_404(item_id, db)
    result = await db.execute(
        select(ClinicalReview)
        .where(ClinicalReview.content_item_id == item_id)
        .order_by(ClinicalReview.created_at.desc())
    )
    return result.scalars().all()


# ---------------------------------------------------------------------------
# Publishing
# ---------------------------------------------------------------------------


@router.post(
    "/items/{item_id}/publish",
    response_model=PublicationRecordRead,
    status_code=status.HTTP_201_CREATED,
)
async def publish_item(
    item_id: uuid.UUID,
    body: PublishRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_permission("content.publish")),
):
    item = await _get_item_or_404(item_id, db)

    if item.status == "retired":
        raise HTTPException(status_code=409, detail="Cannot publish a retired content item")

    if item.current_version_id is None:
        raise HTTPException(status_code=409, detail="Cannot publish: item has no version")

    # Approved review must be for the current version (or have no version specified)
    approved_count = await db.scalar(
        select(func.count(ClinicalReview.id)).where(
            ClinicalReview.content_item_id == item_id,
            ClinicalReview.review_decision.in_(["approved", "approved_with_conditions"]),
            or_(
                ClinicalReview.content_version_id == item.current_version_id,
                ClinicalReview.content_version_id.is_(None),
            ),
        )
    )
    if (approved_count or 0) == 0:
        raise HTTPException(
            status_code=409,
            detail=(
                "Cannot publish: item requires at least one approved clinical review "
                "for the current version"
            ),
        )

    # Enforce active region publishing rules
    current_version = await db.get(ContentVersion, item.current_version_id)
    await _enforce_region_rules(item, body.region_code, current_version, db)

    pub = PublicationRecord(
        content_item_id=item_id,
        content_version_id=item.current_version_id,
        region_code=body.region_code,
        published_by=current_user.id,
        publication_status="published",
        reason=body.reason,
    )
    db.add(pub)
    item.status = "published"
    item.updated_at = datetime.now(timezone.utc)

    await db.flush()
    await log_action(
        db,
        action="content.published",
        actor_user_id=current_user.id,
        resource_type="content_item",
        resource_id=str(item_id),
        details={"region_code": body.region_code, "publication_id": str(pub.id)},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(pub)
    return pub


@router.post(
    "/items/{item_id}/unpublish",
    response_model=PublicationRecordRead,
    status_code=status.HTTP_200_OK,
)
async def unpublish_item(
    item_id: uuid.UUID,
    body: UnpublishRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_permission("content.unpublish")),
):
    item = await _get_item_or_404(item_id, db)

    pub_result = await db.execute(
        select(PublicationRecord).where(
            PublicationRecord.content_item_id == item_id,
            PublicationRecord.region_code == body.region_code,
            PublicationRecord.publication_status == "published",
        )
    )
    pub = pub_result.scalars().first()
    if pub is None:
        raise HTTPException(status_code=409, detail="Item is not published in this region")

    pub.publication_status = "unpublished"
    pub.unpublished_by = current_user.id
    pub.unpublished_at = datetime.now(timezone.utc)
    if body.reason:
        pub.reason = body.reason

    item.status = "unpublished"
    item.updated_at = datetime.now(timezone.utc)

    await log_action(
        db,
        action="content.unpublished",
        actor_user_id=current_user.id,
        resource_type="content_item",
        resource_id=str(item_id),
        details={"region_code": body.region_code, "publication_id": str(pub.id)},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(pub)
    return pub


@router.get("/published", response_model=ContentItemListResponse)
async def list_published(
    region: str = Query(...),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    content_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if region not in REGION_CODES:
        raise HTTPException(status_code=422, detail=f"region must be one of {sorted(REGION_CODES)}")

    q = (
        select(ContentItem)
        .join(PublicationRecord, PublicationRecord.content_item_id == ContentItem.id)
        .where(
            PublicationRecord.region_code == region,
            PublicationRecord.publication_status == "published",
            ContentItem.status == "published",
        )
        .distinct()
    )

    if content_type:
        if content_type not in CONTENT_TYPES:
            raise HTTPException(status_code=422, detail=f"Invalid content_type: {content_type}")
        q = q.where(ContentItem.content_type == content_type)

    count_result = await db.execute(select(func.count()).select_from(q.subquery()))
    total = count_result.scalar_one()
    pages = math.ceil(total / per_page) if per_page else 1
    offset = (page - 1) * per_page
    rows = (
        await db.execute(
            q.order_by(ContentItem.updated_at.desc()).offset(offset).limit(per_page)
        )
    ).scalars().all()

    return ContentItemListResponse(
        items=[ContentItemListItem.model_validate(r) for r in rows],
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
    )


# ---------------------------------------------------------------------------
# Import stubs (Phase 4 bulk import — not yet implemented)
# ---------------------------------------------------------------------------


@router.post("/import/preview", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def import_preview(
    current_user: User = Depends(require_content_permission("content.import")),
):
    raise HTTPException(status_code=501, detail="Bulk import not yet implemented")


@router.post("/import/commit", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def import_commit(
    current_user: User = Depends(require_content_permission("content.import")),
):
    raise HTTPException(status_code=501, detail="Bulk import not yet implemented")

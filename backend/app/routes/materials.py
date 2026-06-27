import math
import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models import Material, Scenario
from app.schemas.schemas import MaterialListItem, MaterialListResponse, MaterialResponse
from app.services.document_parser import extract_text
from app.utils.validators import FileValidationError, build_upload_path, validate_upload_file

router = APIRouter(prefix="/api/materials", tags=["materials"])
settings = get_settings()


async def _process_and_store_text(material_id: uuid.UUID, file_bytes: bytes, filename: str) -> None:
    """Background task: extract text and persist it."""
    from app.database import SessionLocal

    async with SessionLocal() as session:
        result = await session.get(Material, material_id)
        if result is None:
            return
        text = extract_text(file_bytes, filename)
        result.content_text = text or None
        await session.commit()


@router.post(
    "/upload",
    response_model=MaterialResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a clinical study material",
)
async def upload_material(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form(..., min_length=1, max_length=255),
    description: str = Form(default=""),
    db: AsyncSession = Depends(get_db),
) -> MaterialResponse:
    # ── Validate ──────────────────────────────────────────────────────────────
    try:
        validate_upload_file(file)
    except FileValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    file_bytes = await file.read()
    if len(file_bytes) > settings.max_upload_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of {settings.max_upload_size // 1_048_576} MB.",
        )

    # ── Persist file ──────────────────────────────────────────────────────────
    safe_stem = Path(file.filename or "upload").stem  # type: ignore[arg-type]
    unique_name = f"{uuid.uuid4().hex}_{safe_stem}{Path(file.filename or '').suffix}"  # type: ignore[arg-type]
    dest = build_upload_path(unique_name)

    async with aiofiles.open(dest, "wb") as out:
        await out.write(file_bytes)

    # ── Create DB record ──────────────────────────────────────────────────────
    ext = Path(file.filename or "").suffix.lstrip(".").lower()  # type: ignore[arg-type]
    material = Material(
        title=title.strip(),
        description=description.strip() or None,
        file_name=file.filename,
        file_path=str(dest),
        file_size=len(file_bytes),
        file_type=ext,
    )
    db.add(material)
    await db.flush()  # get the generated ID

    # ── Queue text extraction ─────────────────────────────────────────────────
    background_tasks.add_task(_process_and_store_text, material.id, file_bytes, file.filename or "")
    await db.commit()
    await db.refresh(material)

    return MaterialResponse.model_validate(material)


@router.get(
    "",
    response_model=MaterialListResponse,
    summary="List all uploaded materials",
)
async def list_materials(
    page: int = 1,
    per_page: int = 20,
    db: AsyncSession = Depends(get_db),
) -> MaterialListResponse:
    if page < 1:
        page = 1
    if per_page < 1 or per_page > 100:
        per_page = 20

    offset = (page - 1) * per_page

    total_result = await db.execute(select(func.count(Material.id)))
    total: int = total_result.scalar_one()

    materials_result = await db.execute(
        select(Material).order_by(Material.created_at.desc()).offset(offset).limit(per_page)
    )
    materials = materials_result.scalars().all()

    # Fetch scenario counts per material in one query
    scenario_counts_result = await db.execute(
        select(Scenario.material_id, func.count(Scenario.id).label("count"))
        .group_by(Scenario.material_id)
    )
    scenario_counts = {row.material_id: row.count for row in scenario_counts_result}

    items = []
    for m in materials:
        item = MaterialListItem(
            id=m.id,
            title=m.title,
            description=m.description,
            file_name=m.file_name,
            file_size=m.file_size,
            file_type=m.file_type,
            has_content=bool(m.content_text),
            scenario_count=scenario_counts.get(m.id, 0),
            created_at=m.created_at,
        )
        items.append(item)

    return MaterialListResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        pages=math.ceil(total / per_page) if total else 0,
    )


@router.get(
    "/{material_id}",
    response_model=MaterialResponse,
    summary="Get a specific material by ID",
)
async def get_material(
    material_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> MaterialResponse:
    material = await db.get(Material, material_id)
    if material is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found.")
    return MaterialResponse.model_validate(material)


@router.delete(
    "/{material_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a material and its associated scenarios",
)
async def delete_material(
    material_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    material = await db.get(Material, material_id)
    if material is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found.")

    # Remove file from disk
    try:
        Path(material.file_path).unlink(missing_ok=True)
    except Exception:
        pass

    await db.delete(material)
    await db.commit()

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.schemas.content import MaterialResponse  # noqa: F401 — re-exported for convenience


class ScenarioGenerateRequest(BaseModel):
    material_id: uuid.UUID
    difficulty_level: str = Field(default="intermediate")
    specialty: Optional[str] = None

    @field_validator("difficulty_level")
    @classmethod
    def validate_difficulty(cls, v: str) -> str:
        allowed = {"beginner", "intermediate", "advanced"}
        if v.lower() not in allowed:
            raise ValueError(f"difficulty_level must be one of: {allowed}")
        return v.lower()


class ScenarioResponse(BaseModel):
    id: uuid.UUID
    material_id: Optional[uuid.UUID]
    title: str
    clinical_case: str
    difficulty_level: str
    specialty: Optional[str]
    key_concepts: Optional[List[str]]
    interaction_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ScenarioListItem(BaseModel):
    id: uuid.UUID
    material_id: Optional[uuid.UUID]
    title: str
    difficulty_level: str
    specialty: Optional[str]
    key_concepts: Optional[List[str]]
    interaction_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class ScenarioListResponse(BaseModel):
    items: List[ScenarioListItem]
    total: int
    page: int
    per_page: int
    pages: int


class InteractionCreate(BaseModel):
    scenario_id: uuid.UUID
    content: str = Field(..., min_length=10, max_length=10_000)
    session_id: Optional[str] = None

    @field_validator("content")
    @classmethod
    def sanitize_content(cls, v: str) -> str:
        return v.strip()


class InteractionResponse(BaseModel):
    id: uuid.UUID
    scenario_id: uuid.UUID
    user_answer: str
    ai_feedback: str
    score: Optional[float]
    key_findings: Optional[List[str]]
    next_steps: Optional[List[str]]
    strengths: Optional[List[str]]
    areas_for_improvement: Optional[List[str]]
    created_at: datetime

    model_config = {"from_attributes": True}


class ScenarioInteractionsResponse(BaseModel):
    scenario: ScenarioResponse
    interactions: List[InteractionResponse]
    average_score: Optional[float]
    total_interactions: int

"""Learner-facing Pydantic schemas — never expose admin/reviewer internals."""
import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.models.governance import REGION_CODES, CONTENT_TYPES


# ---------------------------------------------------------------------------
# Published content browse
# ---------------------------------------------------------------------------

class LearnableContentItem(BaseModel):
    """Safe list item for learners — no admin metadata."""
    id: uuid.UUID
    external_id: Optional[str]
    title: str
    content_type: str
    domain: Optional[str]
    specialty: Optional[str]
    difficulty: Optional[str]
    region_scope: Optional[list[str]]
    published_at: datetime
    version_id: uuid.UUID
    version_number: int


class LearnableContentListResponse(BaseModel):
    items: list[LearnableContentItem]
    total: int
    page: int
    page_size: int
    pages: int


# ---------------------------------------------------------------------------
# Published content detail
# ---------------------------------------------------------------------------

class LearnableContentDetail(BaseModel):
    """Detail view for a published content item — answer keys stripped."""
    id: uuid.UUID
    external_id: Optional[str]
    title: str
    content_type: str
    domain: Optional[str]
    specialty: Optional[str]
    difficulty: Optional[str]
    region_scope: Optional[list[str]]
    published_at: datetime
    version_id: uuid.UUID
    version_number: int
    # payload with answer/scoring keys removed — never leak before attempt
    safe_payload: Optional[dict[str, Any]]
    evidence_ids: Optional[list[str]]
    localization_notes: Optional[str]
    requires_local_disclaimer: bool
    requires_protocol_note: bool


# ---------------------------------------------------------------------------
# Learner attempt
# ---------------------------------------------------------------------------

class LearnerAttemptCreate(BaseModel):
    region_code: str
    attempt_type: Optional[str] = Field(default=None, max_length=50)
    learner_response: Optional[str] = Field(default=None, max_length=5000)
    selected_action: Optional[str] = Field(default=None, max_length=500)
    time_to_decision_seconds: Optional[int] = Field(default=None, ge=0, le=86400)
    self_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    # Explicit learner-reported dimension flags — None means "not applicable"
    red_flag_identified: Optional[bool] = None
    counseling_point_selected: Optional[bool] = None
    interaction_detected: Optional[bool] = None
    referral_decision_selected: Optional[bool] = None
    dose_calculation_answer: Optional[str] = Field(default=None, max_length=200)
    documentation_completed: Optional[bool] = None

    def valid_region(self) -> bool:
        return self.region_code in REGION_CODES


class LearnerAttemptResult(BaseModel):
    attempt_id: uuid.UUID
    score: Optional[float]
    feedback: str
    failed_dimensions: list[str]
    recommended_next_step: str


# ---------------------------------------------------------------------------
# Learner progress
# ---------------------------------------------------------------------------

class LearnerRecentAttempt(BaseModel):
    id: uuid.UUID
    content_item_id: uuid.UUID
    content_title: Optional[str]
    content_type: Optional[str]
    region_code: Optional[str]
    score: Optional[float]
    attempt_type: Optional[str]
    created_at: datetime


class LearnerProgressSummary(BaseModel):
    total_attempts: int
    average_score: Optional[float]
    attempts_by_content_type: dict[str, int]
    weakness_breakdown: dict[str, float]
    recent_attempts: list[LearnerRecentAttempt]

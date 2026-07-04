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
# Training flow (pre-submission step blueprint)
# ---------------------------------------------------------------------------

class TrainingFlowStep(BaseModel):
    """One step in the guided training flow. Contains no hidden fields."""
    step_number: int
    step_type: str         # "briefing" | "red_flag_check" | "decision" | "counseling"
    title: str
    instruction: str
    safe_content: dict[str, Any]    # safe subset of payload for this step
    input_required: bool
    input_type: str        # "none" | "text" | "action_select" | "checkbox_list"
    options: list[str]     # choices for action_select / checkbox_list


class TrainingFlowResponse(BaseModel):
    content_item_id: uuid.UUID
    content_type: str
    title: str
    total_steps: int
    steps: list[TrainingFlowStep]
    scoring_note: str


# ---------------------------------------------------------------------------
# Training sessions
# ---------------------------------------------------------------------------

class SessionStartRequest(BaseModel):
    # Optional in GLOBAL_CONTENT_MODE — defaults to "GLOBAL" sentinel.
    region_code: Optional[str] = Field(default=None)

    def resolved_region(self) -> str:
        return self.region_code or "GLOBAL"

    def valid_region(self) -> bool:
        rc = self.region_code
        return rc is None or rc == "GLOBAL" or rc in REGION_CODES


class SessionStartResponse(BaseModel):
    session_id: uuid.UUID
    content_item_id: uuid.UUID
    content_version_id: uuid.UUID
    region_code: str
    status: str
    current_step: int
    total_steps: int
    started_at: datetime


class SessionSubmitRequest(BaseModel):
    red_flags_selected: Optional[list[str]] = None
    action_selected: Optional[str] = Field(default=None, max_length=500)
    counseling_points: Optional[list[str]] = None
    documentation_points: Optional[list[str]] = None
    answer_text: Optional[str] = Field(default=None, max_length=5000)
    confidence: Optional[int] = Field(default=None, ge=1, le=5)
    time_to_decision_seconds: Optional[int] = Field(default=None, ge=0, le=86400)


class DimensionFeedbackItem(BaseModel):
    dimension: str
    status: str     # "passed" | "failed" | "not_assessable"
    feedback: str


class SessionSubmitResponse(BaseModel):
    session_id: uuid.UUID
    status: str                             # "completed"
    score: Optional[float]
    max_score: float
    score_percent: Optional[float]
    failed_dimensions: list[str]
    not_assessable_dimensions: list[str]
    dimension_feedback: list[DimensionFeedbackItem]
    reveal_summary: dict[str, Any]          # safe post-submission payload reveal
    next_recommendation: str


# ---------------------------------------------------------------------------
# Learner attempt (Phase 1 — kept for backwards compat)
# ---------------------------------------------------------------------------

class LearnerAttemptCreate(BaseModel):
    # Optional in GLOBAL_CONTENT_MODE — defaults to "GLOBAL" sentinel.
    region_code: Optional[str] = Field(default=None)
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
        rc = self.region_code
        return rc is None or rc == "GLOBAL" or rc in REGION_CODES


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


class LearnerSessionSummary(BaseModel):
    id: uuid.UUID
    content_item_id: uuid.UUID
    content_title: Optional[str]
    content_type: Optional[str]
    region_code: str
    status: str
    score: Optional[float]
    score_percent: Optional[float]
    started_at: datetime
    completed_at: Optional[datetime]


class LearnerProgressSummary(BaseModel):
    total_attempts: int
    completed_sessions: int
    average_score: Optional[float]          # 0.0–1.0 from LearnerFailureAnalytics
    average_score_percent: Optional[float]  # 0–100 from LearnerTrainingSession
    strongest_dimension: Optional[str]
    weakest_dimension: Optional[str]
    attempts_by_content_type: dict[str, int]
    dimension_breakdown: dict[str, float]   # dimension -> fail_rate
    weakness_breakdown: dict[str, float]    # alias kept for compatibility
    recent_attempts: list[LearnerRecentAttempt]
    recent_sessions: list[LearnerSessionSummary]
    recommended_next_content_type: Optional[str]
    recommended_next_domain: Optional[str]

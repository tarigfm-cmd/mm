"""
Deterministic training engine — no AI, no invented clinical content.

Scores learner submissions against structured fields already present in
ContentVersion.payload_json. Marks dimensions as not_assessable when no
structured expected answer exists in the payload.
"""
import dataclasses
from typing import Optional

# ---------------------------------------------------------------------------
# Answer keys that must never appear before submission
# ---------------------------------------------------------------------------

REVEAL_KEYS: frozenset[str] = frozenset({
    "correct_answer_or_expected_response",
    "expected_decision",
    "expected_pharmacist_action",
    "hidden_risk",
    "failure_mode",
    "critical_fail",
    "scoring_rubric",
})

_REVEAL_LABELS: dict[str, str] = {
    "correct_answer_or_expected_response": "Expected answer",
    "expected_decision": "Expected decision",
    "expected_pharmacist_action": "Expected pharmacist action",
    "hidden_risk": "Hidden risk",
    "failure_mode": "Common failure modes",
    "critical_fail": "Critical fail criteria",
    "scoring_rubric": "Scoring rubric",
}

# ---------------------------------------------------------------------------
# Scoring dimensions
# ---------------------------------------------------------------------------

DIMENSION_LABELS: dict[str, str] = {
    "red_flag_recognition": "Red Flag Recognition",
    "triage_or_referral_decision": "Triage / Referral Decision",
    "medication_safety": "Medication Safety",
    "counseling_quality": "Counseling Quality",
    "documentation_quality": "Documentation Quality",
    "calculation_accuracy": "Calculation Accuracy",
    "interaction_detection": "Interaction Detection",
    "communication_safety": "Communication Safety",
}

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class DimensionResult:
    dimension: str
    status: str   # "passed" | "failed" | "not_assessable"
    feedback: str


@dataclasses.dataclass
class ScoringResult:
    score: Optional[float]          # 0.0–1.0; None if no scoreable dimensions
    max_score: float                 # always 1.0
    score_percent: Optional[float]
    failed_dimensions: list[str]
    not_assessable_dimensions: list[str]
    dimension_results: list[DimensionResult]
    reveal_summary: dict            # revealed payload fields, safe after submission
    next_recommendation: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalize(s: str) -> str:
    """Lower-case, strip, collapse whitespace. Safe comparison only."""
    return " ".join(str(s).strip().lower().split())


def _not_assessable(dimension: str) -> DimensionResult:
    return DimensionResult(
        dimension=dimension,
        status="not_assessable",
        feedback=(
            f"{DIMENSION_LABELS.get(dimension, dimension)} cannot be scored "
            "automatically for this content type."
        ),
    )


def _build_reveal_summary(payload: dict) -> dict:
    return {
        _REVEAL_LABELS[k]: v
        for k, v in payload.items()
        if k in REVEAL_KEYS and v is not None
    }


# ---------------------------------------------------------------------------
# Scoring engine
# ---------------------------------------------------------------------------


def score_submission(
    content_type: str,
    payload: dict,
    *,
    action_selected: Optional[str] = None,
    answer_text: Optional[str] = None,
    red_flags_selected: Optional[list[str]] = None,
    counseling_points: Optional[list[str]] = None,
    documentation_points: Optional[list[str]] = None,
    confidence: Optional[int] = None,
    time_to_decision_seconds: Optional[int] = None,
) -> ScoringResult:
    """Score a learner submission deterministically.

    - Scores only where structured expected values exist in the payload.
    - All other dimensions are marked not_assessable (not penalised).
    - Never uses AI or invents clinical content.
    """
    results: list[DimensionResult] = []
    scoreable: list[DimensionResult] = []  # only passed/failed entries

    # ── Triage / Referral Decision (case) ─────────────────────────────────
    expected_decision = payload.get("expected_decision")
    if expected_decision is not None:
        if action_selected:
            if _normalize(action_selected) == _normalize(expected_decision):
                r = DimensionResult(
                    "triage_or_referral_decision", "passed",
                    "Correct — your decision matches the expected pharmacist decision.",
                )
            else:
                r = DimensionResult(
                    "triage_or_referral_decision", "failed",
                    f"Decision did not match. Expected: {expected_decision}.",
                )
            scoreable.append(r)
        else:
            r = DimensionResult(
                "triage_or_referral_decision", "not_assessable",
                "No decision submitted for this dimension.",
            )
        results.append(r)
    else:
        results.append(_not_assessable("triage_or_referral_decision"))

    # ── Medication Safety (prescription_screening) ─────────────────────────
    expected_action = payload.get("expected_pharmacist_action")
    if expected_action is not None:
        if action_selected:
            if _normalize(action_selected) == _normalize(expected_action):
                r = DimensionResult(
                    "medication_safety", "passed",
                    "Correct — your intervention matches the expected pharmacist action.",
                )
            else:
                r = DimensionResult(
                    "medication_safety", "failed",
                    f"Action did not match. Expected: {expected_action}.",
                )
            scoreable.append(r)
        else:
            r = DimensionResult(
                "medication_safety", "not_assessable",
                "No action submitted for this dimension.",
            )
        results.append(r)
    else:
        results.append(_not_assessable("medication_safety"))

    # ── Calculation Accuracy (drill) ───────────────────────────────────────
    correct_answer = payload.get("correct_answer_or_expected_response")
    if correct_answer is not None:
        if answer_text:
            if _normalize(answer_text) == _normalize(correct_answer):
                r = DimensionResult(
                    "calculation_accuracy", "passed",
                    "Correct — your answer matches the expected response.",
                )
            else:
                r = DimensionResult(
                    "calculation_accuracy", "failed",
                    f"Incorrect. The expected response was: {correct_answer}.",
                )
            scoreable.append(r)
        else:
            r = DimensionResult(
                "calculation_accuracy", "not_assessable",
                "No answer submitted for this dimension.",
            )
        results.append(r)
    else:
        results.append(_not_assessable("calculation_accuracy"))

    # ── Red Flag Recognition ───────────────────────────────────────────────
    # Cannot verify without a structured expected red flags list in payload.
    if red_flags_selected is not None:
        results.append(DimensionResult(
            "red_flag_recognition", "not_assessable",
            f"Red flag assessment recorded ({len(red_flags_selected)} flag(s) selected). "
            "Supervisor review recommended.",
        ))
    else:
        results.append(_not_assessable("red_flag_recognition"))

    # ── Counseling Quality ─────────────────────────────────────────────────
    if counseling_points and len(counseling_points) > 0:
        results.append(DimensionResult(
            "counseling_quality", "not_assessable",
            f"Counseling documented ({len(counseling_points)} point(s)). "
            "Automated verification not available.",
        ))
    else:
        results.append(_not_assessable("counseling_quality"))

    # ── Documentation Quality ──────────────────────────────────────────────
    if documentation_points and len(documentation_points) > 0:
        results.append(DimensionResult(
            "documentation_quality", "not_assessable",
            f"Documentation recorded ({len(documentation_points)} item(s)). "
            "Automated verification not available.",
        ))
    else:
        results.append(_not_assessable("documentation_quality"))

    # ── Interaction Detection ──────────────────────────────────────────────
    results.append(_not_assessable("interaction_detection"))

    # ── Communication Safety ───────────────────────────────────────────────
    results.append(_not_assessable("communication_safety"))

    # ── Aggregate ─────────────────────────────────────────────────────────
    failed_dims = [r.dimension for r in results if r.status == "failed"]
    not_assessable_dims = [r.dimension for r in results if r.status == "not_assessable"]
    passed_scoreable = [r for r in scoreable if r.status == "passed"]

    if scoreable:
        score = len(passed_scoreable) / len(scoreable)
        score_percent = round(score * 100, 1)
    else:
        score = None
        score_percent = None

    reveal_summary = _build_reveal_summary(payload)

    # Next recommendation derived from result, not from clinical content
    if score is not None and score >= 0.8:
        next_recommendation = "Excellent — try a more challenging item in this domain."
    elif score is not None and score >= 0.5:
        next_recommendation = "Good attempt — review the highlighted dimensions and retry."
    elif score == 0.0:
        next_recommendation = "Review the expected answer and retry this item."
    elif failed_dims:
        labels = [DIMENSION_LABELS.get(d, d) for d in failed_dims[:2]]
        next_recommendation = f"Focus on: {', '.join(labels)}."
    elif not scoreable:
        next_recommendation = (
            "Guided training recorded. Automated scoring is not available for this "
            "content type — supervisor review is recommended."
        )
    else:
        next_recommendation = "Complete more items to build your weakness profile."

    return ScoringResult(
        score=score,
        max_score=1.0,
        score_percent=score_percent,
        failed_dimensions=failed_dims,
        not_assessable_dimensions=not_assessable_dims,
        dimension_results=results,
        reveal_summary=reveal_summary,
        next_recommendation=next_recommendation,
    )


# ---------------------------------------------------------------------------
# Training flow builder
# ---------------------------------------------------------------------------


def build_training_flow(content_type: str, payload: dict) -> list[dict]:
    """Build ordered pre-submission training steps for a content item.

    Hidden/reveal fields are NEVER included in step content.
    Post-submission reveal steps are NOT returned here — they come back
    in the submit response as reveal_summary.
    """

    def _safe_slice(*keys: str) -> dict:
        return {
            k: payload[k]
            for k in keys
            if k in payload and payload[k] is not None and k not in REVEAL_KEYS
        }

    if content_type == "case":
        return [
            {
                "step_number": 1,
                "step_type": "briefing",
                "title": "Patient Briefing",
                "instruction": (
                    "Read the patient information carefully before deciding on your action."
                ),
                "safe_content": _safe_slice(
                    "patient_profile", "presenting_complaint", "context", "domain", "subtopic"
                ),
                "input_required": False,
                "input_type": "none",
                "options": [],
            },
            {
                "step_number": 2,
                "step_type": "red_flag_check",
                "title": "Red Flag Assessment",
                "instruction": (
                    "List any red flags or alarm symptoms you have identified "
                    "from this patient presentation."
                ),
                "safe_content": {},
                "input_required": True,
                "input_type": "text",
                "options": [],
            },
            {
                "step_number": 3,
                "step_type": "decision",
                "title": "Pharmacist Decision",
                "instruction": "What is your recommended pharmacist action for this patient?",
                "safe_content": {},
                "input_required": True,
                "input_type": "action_select",
                "options": [
                    "Refer to GP",
                    "Treat with OTC product",
                    "Advise only",
                    "Refer urgently",
                    "Dispense with counseling",
                ],
            },
            {
                "step_number": 4,
                "step_type": "counseling",
                "title": "Counseling & Documentation",
                "instruction": (
                    "Which counseling points would you address with this patient?"
                ),
                "safe_content": {},
                "input_required": True,
                "input_type": "checkbox_list",
                "options": [
                    "Warn of side effects",
                    "Explain dosing",
                    "Advise on follow-up",
                    "Document interaction",
                    "Note allergy",
                    "Provide lifestyle advice",
                ],
            },
        ]

    if content_type == "prescription_screening":
        return [
            {
                "step_number": 1,
                "step_type": "briefing",
                "title": "Prescription Review",
                "instruction": "Review the prescription details carefully.",
                "safe_content": _safe_slice(
                    "patient_profile", "context", "safety_concern", "domain", "subtopic"
                ),
                "input_required": False,
                "input_type": "none",
                "options": [],
            },
            {
                "step_number": 2,
                "step_type": "red_flag_check",
                "title": "Safety Concern Identification",
                "instruction": (
                    "Identify any safety concerns, contraindications, or interaction risks."
                ),
                "safe_content": {},
                "input_required": True,
                "input_type": "text",
                "options": [],
            },
            {
                "step_number": 3,
                "step_type": "decision",
                "title": "Pharmacist Intervention",
                "instruction": "What is the required pharmacist action?",
                "safe_content": {},
                "input_required": True,
                "input_type": "action_select",
                "options": [
                    "Dispense as prescribed",
                    "Dispense with counseling",
                    "Query with prescriber",
                    "Refer back to prescriber",
                    "Withhold and refer urgently",
                ],
            },
            {
                "step_number": 4,
                "step_type": "counseling",
                "title": "Patient Communication & Documentation",
                "instruction": (
                    "What would you communicate to the patient and document in the record?"
                ),
                "safe_content": {},
                "input_required": True,
                "input_type": "checkbox_list",
                "options": [
                    "Explain reason for query",
                    "Counsel on alternative",
                    "Document in PMR",
                    "Note allergy/contraindication",
                    "Advise follow-up",
                ],
            },
        ]

    if content_type == "drill":
        return [
            {
                "step_number": 1,
                "step_type": "briefing",
                "title": "Question",
                "instruction": "Read the prompt carefully and prepare your answer.",
                "safe_content": _safe_slice("prompt", "context", "domain", "subtopic"),
                "input_required": False,
                "input_type": "none",
                "options": [],
            },
            {
                "step_number": 2,
                "step_type": "decision",
                "title": "Your Answer",
                "instruction": "Enter your answer below.",
                "safe_content": {},
                "input_required": True,
                "input_type": "text",
                "options": [],
            },
        ]

    if content_type == "osce_station":
        return [
            {
                "step_number": 1,
                "step_type": "briefing",
                "title": "Station Brief",
                "instruction": (
                    "Read the candidate task and station setup carefully before beginning."
                ),
                "safe_content": _safe_slice(
                    "station_title", "candidate_task", "context", "patient_profile"
                ),
                "input_required": False,
                "input_type": "none",
                "options": [],
            },
            {
                "step_number": 2,
                "step_type": "decision",
                "title": "Communication Checklist",
                "instruction": (
                    "Which communication elements did you address during your consultation?"
                ),
                "safe_content": {},
                "input_required": True,
                "input_type": "checkbox_list",
                "options": [
                    "Introduced myself",
                    "Checked patient ID",
                    "Explained purpose",
                    "Demonstrated empathy",
                    "Summarised plan",
                    "Checked patient understanding",
                ],
            },
        ]

    if content_type == "simulation":
        return [
            {
                "step_number": 1,
                "step_type": "briefing",
                "title": "Patient Encounter",
                "instruction": (
                    "Read the patient opening statement and prepare your response."
                ),
                "safe_content": _safe_slice(
                    "patient_profile", "presenting_complaint", "context"
                ),
                "input_required": False,
                "input_type": "none",
                "options": [],
            },
            {
                "step_number": 2,
                "step_type": "red_flag_check",
                "title": "Risk Identification",
                "instruction": "What risks or safety concerns have you identified?",
                "safe_content": {},
                "input_required": True,
                "input_type": "text",
                "options": [],
            },
            {
                "step_number": 3,
                "step_type": "decision",
                "title": "Your Response / Action",
                "instruction": "Describe your pharmacist response or recommended action.",
                "safe_content": {},
                "input_required": True,
                "input_type": "text",
                "options": [],
            },
        ]

    # Fallback (game, evidence_source, taxonomy_node, etc.)
    safe_content = {
        k: v for k, v in payload.items() if k not in REVEAL_KEYS and v is not None
    }
    return [
        {
            "step_number": 1,
            "step_type": "briefing",
            "title": "Content Review",
            "instruction": "Review the content below.",
            "safe_content": safe_content,
            "input_required": False,
            "input_type": "none",
            "options": [],
        },
    ]

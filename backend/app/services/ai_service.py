"""AI service for generating pharmacy clinical scenarios using Anthropic Claude."""

import json
import logging
from typing import Any

import anthropic

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_SYSTEM_PROMPT = """You are an expert pharmacy educator and clinical pharmacist with 20+ years of experience in \
community and clinical pharmacy practice. You specialize in creating realistic, evidence-based case studies \
for pharmacy education (undergraduate, postgraduate, and CPD).

Your clinical scenarios:
- Are grounded in current clinical guidelines and pharmacological evidence
- Reflect realistic community/clinical pharmacy encounters
- Test genuine competencies: drug therapy optimization, patient counseling, OTC triage, drug interactions, \
  adverse effect monitoring, dose calculations, and medication reconciliation
- Use appropriate medical terminology while remaining educationally clear
- Are appropriate for the requested difficulty level

When generating content always return ONLY valid JSON — no markdown fences, no prose outside the JSON object."""

_GENERATE_PROMPT = """\
Study material content:
---
{content}
---

Generate a {difficulty_level}-level community pharmacy clinical scenario based on the above material.

Return a JSON object with exactly these fields:
{{
  "title": "<concise scenario title, max 80 chars>",
  "clinical_case": "<full case presentation: patient demographics, presenting complaint, relevant \
PMH, current medications, examination findings, and 2–4 focused clinical questions for the pharmacy student>",
  "specialty": "<one of: dispensing | clinical-review | patient-counselling | otc-triage | drug-information | \
medication-reconciliation | pharmacokinetics>",
  "key_concepts": ["<concept 1>", "<concept 2>", "<concept 3>"],
  "expected_answer": "<comprehensive model answer covering all clinical questions, referencing pharmacological \
rationale and relevant guidelines>"
}}"""

_EVALUATE_PROMPT = """\
You are evaluating a pharmacy student's response to a clinical case.

Clinical Case:
---
{clinical_case}
---

Model Answer (reference only — do not reveal to student):
---
{expected_answer}
---

Student Response:
---
{user_answer}
---

Evaluate the response rigorously but fairly. Return a JSON object with exactly these fields:
{{
  "score": <float 0.0–1.0 representing overall competency demonstrated>,
  "feedback": "<2–4 paragraph detailed feedback, written directly to the student>",
  "key_findings": ["<correct finding or reasoning the student identified>"],
  "next_steps": ["<specific learning action or resource for improvement>"],
  "strengths": ["<what the student did well>"],
  "areas_for_improvement": ["<specific gap to address>"]
}}"""


def _get_client() -> anthropic.Anthropic:
    if not settings.anthropic_api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not configured. "
            "Set it in your .env file to enable AI features."
        )
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def _call_claude(prompt: str, temperature: float | None = None) -> dict[str, Any]:
    """Call Claude and parse JSON response. Raises on non-JSON or API error."""
    client = _get_client()
    temp = temperature if temperature is not None else settings.ai_temperature

    message = client.messages.create(
        model=settings.ai_model,
        max_tokens=settings.ai_max_tokens,
        temperature=temp,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()

    # Strip accidental markdown fences
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error("Claude returned non-JSON: %s", raw[:500])
        raise ValueError(f"AI returned invalid JSON: {exc}") from exc


def generate_scenario(
    content_text: str,
    difficulty_level: str = "intermediate",
) -> dict[str, Any]:
    """Generate a pharmacy clinical scenario from extracted document text."""
    truncated = content_text[:12_000]  # stay well within context limits
    prompt = _GENERATE_PROMPT.format(content=truncated, difficulty_level=difficulty_level)
    result = _call_claude(prompt, temperature=0.8)

    required = {"title", "clinical_case", "specialty", "key_concepts", "expected_answer"}
    missing = required - result.keys()
    if missing:
        raise ValueError(f"AI response missing fields: {missing}")

    if not isinstance(result["key_concepts"], list):
        result["key_concepts"] = [result["key_concepts"]]

    return result


def evaluate_answer(
    clinical_case: str,
    expected_answer: str,
    user_answer: str,
) -> dict[str, Any]:
    """Evaluate a student's answer and return structured feedback."""
    prompt = _EVALUATE_PROMPT.format(
        clinical_case=clinical_case,
        expected_answer=expected_answer or "No model answer provided.",
        user_answer=user_answer,
    )
    result = _call_claude(prompt, temperature=0.3)

    required = {"score", "feedback", "key_findings", "next_steps", "strengths", "areas_for_improvement"}
    missing = required - result.keys()
    if missing:
        raise ValueError(f"AI evaluation response missing fields: {missing}")

    # Clamp score
    result["score"] = max(0.0, min(1.0, float(result["score"])))

    for list_field in ("key_findings", "next_steps", "strengths", "areas_for_improvement"):
        if not isinstance(result[list_field], list):
            result[list_field] = [result[list_field]] if result[list_field] else []

    return result

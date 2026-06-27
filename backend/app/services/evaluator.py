"""Thin wrapper — evaluation logic lives in ai_generator to keep the AI layer unified."""

from app.services.ai_generator import evaluate_answer

__all__ = ["evaluate_answer"]

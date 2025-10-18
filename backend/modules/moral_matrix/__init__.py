"""Moral Matrix module public API."""

from .service import MoralMatrixModule
from .types import MoralMatrixResult
from .heuristics import analyze_emotion, generate_instruction

__all__ = ["MoralMatrixModule", "MoralMatrixResult", "analyze_emotion", "generate_instruction"]

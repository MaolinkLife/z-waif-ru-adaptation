"""Compatibility wrapper for legacy imports.

The logic now lives in modules.moral_matrix.heuristics.
"""

from modules.moral_matrix.heuristics import analyze_emotion, generate_instruction

__all__ = ["analyze_emotion", "generate_instruction"]

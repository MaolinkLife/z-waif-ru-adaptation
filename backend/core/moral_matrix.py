"""Compatibility re-export for the old import path.

Prefer importing from ``modules.moral_matrix``.
"""

from modules.moral_matrix import MoralMatrixModule

MoralMatrix = MoralMatrixModule

__all__ = ["MoralMatrix", "MoralMatrixModule"]

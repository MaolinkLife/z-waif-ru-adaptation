"""Provider registry for the MoralMatrix module."""

from .heuristic import HeuristicMoralProvider
from .ollama import OllamaMoralProvider
from .openrouter import OpenRouterMoralProvider

__all__ = ["HeuristicMoralProvider", "OllamaMoralProvider", "OpenRouterMoralProvider"]

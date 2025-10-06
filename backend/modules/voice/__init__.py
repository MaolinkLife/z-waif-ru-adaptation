# modules/voice/__init__.py
"""
Voice module initialization
Exports main voice functionality
"""

from .vad_listener import start_voice_vad_loop

__all__ = ["start_voice_vad_loop"]

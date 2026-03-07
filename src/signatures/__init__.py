# Willow Signatures Module
"""Thought Signature detection and processing components."""

from .thought_signature import ThoughtSignature
from .parser import extract_thought, extract_surface
from .tactic_detector import TacticDetector, TacticDetectionResult

__all__ = [
    "ThoughtSignature",
    "extract_thought",
    "extract_surface",
    "TacticDetector",
    "TacticDetectionResult",
]

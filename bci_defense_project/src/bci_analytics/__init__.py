"""Observation-only BCI analytics for Eagle Eyes.

This package analyzes supplied numeric signal samples. It does not connect to
hardware, stimulate a user, diagnose a condition, or issue commands.
"""

from .engine import (
    BCI_ANALYTICS_VERSION,
    AnalysisResult,
    analyze_signal,
    hamming_distance,
)

__all__ = [
    "BCI_ANALYTICS_VERSION",
    "AnalysisResult",
    "analyze_signal",
    "hamming_distance",
]

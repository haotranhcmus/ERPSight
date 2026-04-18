"""
services/confidence_scorer.py

Composite confidence score for InsightReport.

Formula:
    confidence = w1 * anomaly_score + w2 * similarity_score + w3 * data_coverage
    w1=0.5, w2=0.3, w3=0.2

When FAISS is not available, similarity_score = 0 and weightings auto-adjust:
    confidence = 0.7 * anomaly_score + 0.3 * data_coverage
"""

from __future__ import annotations

import math


def compute_confidence(
    anomaly_score: float,
    similarity_score: float = 0.0,
    data_coverage: float = 1.0,
) -> float:
    """
    Compute a composite confidence score in [0, 1].

    Args:
        anomaly_score:    detection confidence from the detector (0–1)
        similarity_score: cosine similarity with historical incident (0–1), 0 if FAISS unavailable
        data_coverage:    fraction of insight tools that returned data (0–1)
    """
    if similarity_score > 0:
        w1, w2, w3 = 0.5, 0.3, 0.2
        raw = w1 * anomaly_score + w2 * similarity_score + w3 * data_coverage
    else:
        # No FAISS data — redistribute weight to anomaly + coverage
        w1, w3 = 0.7, 0.3
        raw = w1 * anomaly_score + w3 * data_coverage

    return min(max(raw, 0.0), 1.0)

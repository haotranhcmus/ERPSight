"""
memory/faiss_store.py

FAISS-based vector store for incident similarity search.
Stores IncidentRecord metadata alongside FAISS index.
Falls back to empty results when FAISS/sentence-transformers not installed.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from erpsight.backend.memory import embedder
from erpsight.backend.models.incident_record import IncidentRecord

logger = logging.getLogger(__name__)

_FAISS_AVAILABLE = True
_index = None
_records: List[IncidentRecord] = []
_DIM = 384  # all-MiniLM-L6-v2 dimension


def _ensure_index():
    global _index, _FAISS_AVAILABLE
    if _index is not None:
        return
    try:
        import faiss
        _index = faiss.IndexFlatIP(_DIM)  # inner-product (cosine on normalized vectors)
        logger.info("FAISS index initialized (dim=%d)", _DIM)
    except ImportError:
        _FAISS_AVAILABLE = False
        logger.warning("faiss-cpu not installed — similarity search disabled")


def is_available() -> bool:
    _ensure_index()
    return _FAISS_AVAILABLE and embedder.is_available()


def add_incident(record: IncidentRecord) -> None:
    """Add an incident to the FAISS index."""
    _ensure_index()
    if _index is None:
        return

    text = f"{record.anomaly_type} {record.scenario} {record.summary} {record.outcome}"
    vec = embedder.embed_text(text).reshape(1, -1).astype(np.float32)
    _index.add(vec)
    _records.append(record)
    logger.debug("Added incident %s to FAISS (total=%d)", record.incident_id, _index.ntotal)


def search_similar(query_text: str, top_k: int = 3) -> List[Tuple[IncidentRecord, float]]:
    """
    Return up to top_k similar incidents with cosine similarity scores.

    Returns:
        List of (IncidentRecord, similarity_score) tuples, descending by score.
    """
    _ensure_index()
    if _index is None or _index.ntotal == 0:
        return []

    vec = embedder.embed_text(query_text).reshape(1, -1).astype(np.float32)
    scores, indices = _index.search(vec, min(top_k, _index.ntotal))

    results: List[Tuple[IncidentRecord, float]] = []
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0 or idx >= len(_records):
            continue
        results.append((_records[idx], float(score)))

    return results


def get_all_incidents() -> List[IncidentRecord]:
    return list(_records)


def count() -> int:
    if _index is None:
        return 0
    return _index.ntotal

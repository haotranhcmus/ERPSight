"""
memory/embedder.py

Text → vector embedding using sentence-transformers.
Falls back gracefully when the package is not installed.
"""

from __future__ import annotations

import logging
from typing import List

import numpy as np

logger = logging.getLogger(__name__)

_model = None
_AVAILABLE = True


def _load_model():
    global _model, _AVAILABLE
    if _model is not None:
        return _model
    try:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("Loaded sentence-transformers model: all-MiniLM-L6-v2")
    except ImportError:
        _AVAILABLE = False
        logger.warning("sentence-transformers not installed — FAISS memory disabled")
    return _model


def is_available() -> bool:
    _load_model()
    return _AVAILABLE


def embed_texts(texts: List[str]) -> np.ndarray:
    """Return (N, D) float32 numpy array of embeddings."""
    model = _load_model()
    if model is None:
        return np.zeros((len(texts), 384), dtype=np.float32)
    return model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)


def embed_text(text: str) -> np.ndarray:
    """Return (D,) float32 vector."""
    return embed_texts([text])[0]

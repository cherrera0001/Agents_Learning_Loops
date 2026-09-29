"""Normalización de texto y similitud léxica (sin dependencias)."""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter

STOPWORDS = {
    # español
    "el", "la", "los", "las", "de", "del", "en", "para", "por", "con", "un", "una",
    "y", "o", "a", "al", "que", "es", "hoy", "mi", "su",
    # inglés
    "the", "of", "for", "in", "on", "to", "and", "or", "an", "is", "my", "get",
}


def _strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )


def tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9_]+", _strip_accents(text.lower()))
    return [w for w in words if w not in STOPWORDS and len(w) > 1]


def cosine_similarity(a: str, b: str) -> float:
    """Coseno entre bolsas de palabras (normalizadas: minúsculas, sin tildes ni stopwords)."""
    ca, cb = Counter(tokenize(a)), Counter(tokenize(b))
    if not ca or not cb:
        return 0.0
    dot = sum(ca[t] * cb[t] for t in ca)
    return dot / (math.sqrt(sum(v * v for v in ca.values())) * math.sqrt(sum(v * v for v in cb.values())))

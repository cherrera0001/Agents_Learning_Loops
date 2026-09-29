"""Embeddings para la búsqueda híbrida (#3).

- ``LexicalEmbedder``: *feature hashing* de tokens a un vector disperso. No
  tiene dependencias y es determinista (usa ``hashlib``, no ``hash()``, cuyo
  valor cambia entre procesos). Es el valor por defecto y el que usan los tests.
- ``FastEmbedEmbedder``: modelo ONNX local vía ``fastembed`` (extra
  ``[embeddings]``). Captura sinónimos y paráfrasis sin solapamiento léxico.

Cualquier objeto con ``name``, ``dim`` y ``embed(texts)`` sirve como embedder.
"""

from __future__ import annotations

import hashlib
import math
from collections import Counter
from collections.abc import Sequence
from typing import Any, Protocol

from .text import tokenize

Vector = list[float]


class Embedder(Protocol):
    name: str
    dim: int

    def embed(self, texts: Sequence[str]) -> list[Vector]: ...


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


class LexicalEmbedder:
    """Hashing de tokens con signo (Weinberger et al., 2009), normalizado L2."""

    def __init__(self, dim: int = 1024) -> None:
        self.dim = dim
        self.name = f"lexical-hash-{dim}"

    def _bucket(self, token: str) -> tuple[int, float]:
        h = int.from_bytes(hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest(), "big")
        return h % self.dim, (1.0 if (h >> 63) & 1 else -1.0)

    def embed(self, texts: Sequence[str]) -> list[Vector]:
        vectors = []
        for text in texts:
            vec = [0.0] * self.dim
            for token, count in Counter(tokenize(text)).items():
                i, sign = self._bucket(token)
                vec[i] += sign * count
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            vectors.append([v / norm for v in vec])
        return vectors


class FastEmbedEmbedder:
    """Embeddings semánticos locales (ONNX). Requiere ``pip install -e .[embeddings]``.

    El modelo se descarga en la primera llamada y se carga una sola vez.
    """

    DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    def __init__(self, model_name: str = DEFAULT_MODEL) -> None:
        self.name = model_name
        self._model: Any = None  # fastembed.TextEmbedding (import perezoso)
        self.dim = 0

    def _load(self) -> Any:
        if self._model is None:
            from fastembed import TextEmbedding  # import perezoso: extra opcional

            self._model = TextEmbedding(model_name=self.name)
        return self._model

    def embed(self, texts: Sequence[str]) -> list[Vector]:
        vectors = [[float(x) for x in v] for v in self._load().embed(list(texts))]
        if vectors:
            self.dim = len(vectors[0])
        return vectors

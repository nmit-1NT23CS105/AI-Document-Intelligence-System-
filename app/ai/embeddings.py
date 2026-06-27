from __future__ import annotations

import hashlib
import math
import re
from functools import lru_cache
from typing import Protocol

from app.core.config import get_settings

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")

SEMANTIC_NORMALIZATION = {
    "allowance": "days",
    "holiday": "leave",
    "holidays": "leave",
    "vacation": "leave",
    "vacations": "leave",
    "pto": "leave",
    "paid": "pay",
    "payment": "pay",
    "payments": "pay",
}


class EmbeddingModel(Protocol):
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        ...


class LocalEmbeddingModel:
    def __init__(self, dimensions: int = 128) -> None:
        self.dimensions = dimensions

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_text(text) for text in texts]

    def _embed_text(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in TOKEN_PATTERN.findall(text.lower()):
            normalized = SEMANTIC_NORMALIZATION.get(token, token)
            digest = hashlib.sha256(normalized.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            vector[index] += 1.0

        length = math.sqrt(sum(value * value for value in vector))
        if not length:
            return vector
        return [value / length for value in vector]


class SentenceTransformerEmbeddingModel:
    def __init__(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        embeddings = self.model.encode(texts, normalize_embeddings=True)
        return [[float(value) for value in embedding] for embedding in embeddings]


@lru_cache
def get_embedding_model() -> EmbeddingModel:
    settings = get_settings()
    if settings.embedding_provider == "sentence-transformers":
        try:
            return SentenceTransformerEmbeddingModel(settings.embedding_model_name)
        except ImportError:
            return LocalEmbeddingModel()
    return LocalEmbeddingModel()

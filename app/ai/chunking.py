from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    chunk_index: int
    text: str


def chunk_text(text: str, chunk_size: int = 180, overlap: int = 30) -> list[TextChunk]:
    words = text.split()
    if not words:
        return []
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be zero or less than chunk_size")

    chunks: list[TextChunk] = []
    start = 0
    chunk_index = 0
    step = chunk_size - overlap

    while start < len(words):
        end = start + chunk_size
        chunk_words = words[start:end]
        chunks.append(TextChunk(chunk_index=chunk_index, text=" ".join(chunk_words)))
        start += step
        chunk_index += 1

    return chunks

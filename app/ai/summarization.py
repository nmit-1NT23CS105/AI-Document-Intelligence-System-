from __future__ import annotations

import re

SENTENCE_PATTERN = re.compile(r"[^.!?\n]+[.!?]?")


def _looks_like_heading(sentence: str) -> bool:
    words = re.findall(r"[A-Za-z0-9]+", sentence)
    return bool(words) and len(words) <= 8 and sentence[-1:] not in ".!?"


def split_sentences(text: str) -> list[str]:
    sentences = [
        sentence.strip()
        for sentence in SENTENCE_PATTERN.findall(text)
        if sentence.strip()
    ]
    if len(sentences) > 1 and _looks_like_heading(sentences[0]):
        return sentences[1:]
    return sentences


def summarize_text(
    text: str,
    summary_sentence_count: int = 2,
    max_key_points: int = 5,
) -> tuple[str, list[str]]:
    sentences = split_sentences(text)
    if not sentences:
        return "", []

    short_summary = " ".join(sentences[:summary_sentence_count])
    key_points = sentences[:max_key_points]
    return short_summary, key_points

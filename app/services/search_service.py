from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session, joinedload

from app.ai.chunking import chunk_text
from app.ai.embeddings import SEMANTIC_NORMALIZATION, TOKEN_PATTERN, get_embedding_model
from app.core.config import get_settings
from app.database.models import Document, DocumentChunk, User


MAX_SNIPPET_CHARS = 360


@dataclass(frozen=True)
class SearchMatch:
    document_id: int
    filename: str
    chunk_index: int
    snippet: str
    score: float
    category: str = ""
    file_type: str = ""
    highlights: list[str] = field(default_factory=list)
    match_type: str = "Semantic"
    relevance_label: str = "Low"


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return sum(left_value * right_value for left_value, right_value in zip(left, right))


def _normalize_token(token: str) -> str:
    lowered = token.lower()
    return SEMANTIC_NORMALIZATION.get(lowered, lowered)


def _query_tokens(query: str) -> tuple[list[str], set[str]]:
    raw_tokens = TOKEN_PATTERN.findall(query.lower())
    unique_raw = list(dict.fromkeys(raw_tokens))
    normalized = {_normalize_token(token) for token in unique_raw}
    return unique_raw, normalized


def _matched_terms(text: str, normalized_query_tokens: set[str], limit: int = 6) -> list[str]:
    if not normalized_query_tokens:
        return []

    matches: list[str] = []
    seen: set[str] = set()
    for token in TOKEN_PATTERN.findall(text.lower()):
        normalized = _normalize_token(token)
        if normalized in normalized_query_tokens and token not in seen:
            matches.append(token)
            seen.add(token)
        if len(matches) >= limit:
            break
    return matches


def _lexical_match_score(
    text: str,
    filename: str,
    query: str,
) -> tuple[float, list[str], str]:
    raw_query_tokens, normalized_query_tokens = _query_tokens(query)
    if not normalized_query_tokens:
        return 0.0, [], "Semantic"

    lowered_text = text.lower()
    lowered_filename = filename.lower()
    phrase = " ".join(raw_query_tokens).strip()
    exact_phrase = bool(phrase and (phrase in lowered_text or phrase in lowered_filename))

    text_tokens = {_normalize_token(token) for token in TOKEN_PATTERN.findall(lowered_text)}
    filename_tokens = {_normalize_token(token) for token in TOKEN_PATTERN.findall(lowered_filename)}
    text_coverage = len(normalized_query_tokens & text_tokens) / len(normalized_query_tokens)
    filename_coverage = len(normalized_query_tokens & filename_tokens) / len(normalized_query_tokens)

    score = min(1.0, (text_coverage * 0.72) + (filename_coverage * 0.08) + (0.2 if exact_phrase else 0.0))
    highlights = _matched_terms(text, normalized_query_tokens)
    if exact_phrase:
        return max(score, 0.95), highlights, "Exact phrase"
    if text_coverage or filename_coverage:
        return score, highlights, "Keyword + semantic"
    return score, highlights, "Semantic"


def _focused_snippet(text: str, query: str, highlights: list[str]) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= MAX_SNIPPET_CHARS:
        return cleaned

    lowered = cleaned.lower()
    raw_query_tokens, _ = _query_tokens(query)
    phrase = " ".join(raw_query_tokens).strip()
    match_index = lowered.find(phrase) if phrase else -1
    if match_index < 0:
        for term in highlights:
            match_index = lowered.find(term.lower())
            if match_index >= 0:
                break
    if match_index < 0:
        match_index = 0

    context = MAX_SNIPPET_CHARS // 2
    start = max(0, match_index - context)
    end = min(len(cleaned), match_index + context)

    while start > 0 and not cleaned[start].isspace():
        start += 1
    while end < len(cleaned) and not cleaned[end - 1].isspace():
        end -= 1

    snippet = cleaned[start:end].strip()
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(cleaned) else ""
    return f"{prefix}{snippet}{suffix}"


def _relevance_label(score: float, match_type: str) -> str:
    if match_type == "Exact phrase" or score >= 0.65:
        return "High"
    if score >= 0.35:
        return "Medium"
    return "Low"


def _combine_scores(semantic_score: float, lexical_score: float) -> float:
    score = (semantic_score * 0.62) + (lexical_score * 0.38)
    if lexical_score >= 0.95:
        score = max(score, 0.72)
    elif lexical_score >= 0.5:
        score = max(score, 0.45)
    return min(1.0, score)


def _build_match(
    *,
    document_id: int,
    filename: str,
    category: str,
    file_type: str,
    chunk_index: int,
    text: str,
    semantic_score: float,
    query: str,
) -> SearchMatch | None:
    lexical_score, highlights, match_type = _lexical_match_score(
        text=text,
        filename=filename,
        query=query,
    )
    score = _combine_scores(semantic_score=semantic_score, lexical_score=lexical_score)
    if score <= 0:
        return None

    return SearchMatch(
        document_id=document_id,
        filename=filename,
        chunk_index=chunk_index,
        snippet=_focused_snippet(text=text, query=query, highlights=highlights),
        score=round(score, 6),
        category=category,
        file_type=file_type,
        highlights=highlights,
        match_type=match_type,
        relevance_label=_relevance_label(score=score, match_type=match_type),
    )


def _get_chroma_collection() -> Any | None:
    settings = get_settings()
    if settings.vector_store_provider != "chroma":
        return None

    try:
        import chromadb
    except ImportError:
        return None

    client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    return client.get_or_create_collection(name="document_chunks")


def _index_chroma_document(
    document: Document,
    chunks,
    embeddings: list[list[float]],
) -> None:
    collection = _get_chroma_collection()
    if collection is None or not chunks:
        return

    collection.upsert(
        ids=[f"doc-{document.id}-chunk-{chunk.chunk_index}" for chunk in chunks],
        embeddings=embeddings,
        documents=[chunk.text for chunk in chunks],
        metadatas=[
            {
                "document_id": document.id,
                "user_id": document.user_id,
                "filename": document.filename,
                "chunk_index": chunk.chunk_index,
                "category": document.category,
                "file_type": document.file_type,
            }
            for chunk in chunks
        ],
    )


def remove_document_from_index(document_id: int) -> None:
    collection = _get_chroma_collection()
    if collection is None:
        return
    collection.delete(where={"document_id": document_id})


def index_document_text(db: Session, document: Document, extracted_text: str) -> None:
    settings = get_settings()
    chunks = chunk_text(
        extracted_text,
        chunk_size=settings.chunk_size_words,
        overlap=settings.chunk_overlap_words,
    )

    db.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).delete()
    if not chunks:
        db.commit()
        return

    embeddings = get_embedding_model().embed_texts([chunk.text for chunk in chunks])
    _index_chroma_document(document=document, chunks=chunks, embeddings=embeddings)
    for chunk, embedding in zip(chunks, embeddings):
        db.add(
            DocumentChunk(
                document_id=document.id,
                user_id=document.user_id,
                chunk_index=chunk.chunk_index,
                text=chunk.text,
                embedding_json=json.dumps(embedding),
            )
        )

    db.commit()


def _search_chroma(user: User, query: str, limit: int) -> list[SearchMatch] | None:
    collection = _get_chroma_collection()
    if collection is None:
        return None

    query_embedding = get_embedding_model().embed_texts([query])[0]
    raw_results = collection.query(
        query_embeddings=[query_embedding],
        n_results=limit,
        where={"user_id": user.id},
        include=["documents", "metadatas", "distances"],
    )

    documents = raw_results.get("documents", [[]])[0]
    metadatas = raw_results.get("metadatas", [[]])[0]
    distances = raw_results.get("distances", [[]])[0]
    matches: list[SearchMatch] = []

    for text, metadata, distance in zip(documents, metadatas, distances):
        match = _build_match(
            document_id=int(metadata["document_id"]),
            filename=str(metadata["filename"]),
            category=str(metadata.get("category") or ""),
            file_type=str(metadata.get("file_type") or ""),
            chunk_index=int(metadata["chunk_index"]),
            text=str(text),
            semantic_score=max(0.0, 1.0 - float(distance)),
            query=query,
        )
        if match is not None:
            matches.append(match)

    return matches


def search_documents(
    db: Session,
    user: User,
    query: str,
    limit: int,
    document_id: int | None = None,
    category: str | None = None,
) -> list[SearchMatch]:
    chroma_matches = None
    if document_id is None and not category:
        chroma_matches = _search_chroma(user=user, query=query, limit=limit)
    if chroma_matches is not None:
        return chroma_matches

    query_embedding = get_embedding_model().embed_texts([query])[0]
    filters = [DocumentChunk.user_id == user.id]
    if document_id is not None:
        filters.append(DocumentChunk.document_id == document_id)
    if category:
        filters.append(Document.category == category)

    chunks = (
        db.query(DocumentChunk)
        .join(DocumentChunk.document)
        .options(joinedload(DocumentChunk.document))
        .filter(*filters)
        .all()
    )

    matches: list[SearchMatch] = []
    for chunk in chunks:
        chunk_embedding = json.loads(chunk.embedding_json)
        match = _build_match(
            document_id=chunk.document_id,
            filename=chunk.document.filename,
            category=chunk.document.category,
            file_type=chunk.document.file_type,
            chunk_index=chunk.chunk_index,
            text=chunk.text,
            semantic_score=_cosine_similarity(query_embedding, chunk_embedding),
            query=query,
        )
        if match is not None:
            matches.append(match)

    matches.sort(key=lambda match: match.score, reverse=True)
    return matches[:limit]

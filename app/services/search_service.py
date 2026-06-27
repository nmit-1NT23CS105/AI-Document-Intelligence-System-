from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session, joinedload

from app.ai.chunking import chunk_text
from app.ai.embeddings import get_embedding_model
from app.core.config import get_settings
from app.database.models import Document, DocumentChunk, User


@dataclass(frozen=True)
class SearchMatch:
    document_id: int
    filename: str
    chunk_index: int
    snippet: str
    score: float


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return sum(left_value * right_value for left_value, right_value in zip(left, right))


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
        matches.append(
            SearchMatch(
                document_id=int(metadata["document_id"]),
                filename=str(metadata["filename"]),
                chunk_index=int(metadata["chunk_index"]),
                snippet=str(text),
                score=round(max(0.0, 1.0 - float(distance)), 6),
            )
        )

    return matches


def search_documents(
    db: Session,
    user: User,
    query: str,
    limit: int,
    document_id: int | None = None,
) -> list[SearchMatch]:
    chroma_matches = None
    if document_id is None:
        chroma_matches = _search_chroma(user=user, query=query, limit=limit)
    if chroma_matches is not None:
        return chroma_matches

    query_embedding = get_embedding_model().embed_texts([query])[0]
    filters = [DocumentChunk.user_id == user.id]
    if document_id is not None:
        filters.append(DocumentChunk.document_id == document_id)

    chunks = (
        db.query(DocumentChunk)
        .options(joinedload(DocumentChunk.document))
        .filter(*filters)
        .all()
    )

    matches: list[SearchMatch] = []
    for chunk in chunks:
        chunk_embedding = json.loads(chunk.embedding_json)
        score = _cosine_similarity(query_embedding, chunk_embedding)
        if score <= 0:
            continue

        matches.append(
            SearchMatch(
                document_id=chunk.document_id,
                filename=chunk.document.filename,
                chunk_index=chunk.chunk_index,
                snippet=chunk.text,
                score=round(score, 6),
            )
        )

    matches.sort(key=lambda match: match.score, reverse=True)
    return matches[:limit]

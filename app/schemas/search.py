from __future__ import annotations

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=5, ge=1, le=20)


class SearchResult(BaseModel):
    document_id: int
    filename: str
    chunk_index: int
    snippet: str
    score: float


class SearchResponse(BaseModel):
    results: list[SearchResult]

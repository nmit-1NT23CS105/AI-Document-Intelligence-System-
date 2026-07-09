from __future__ import annotations

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=5, ge=1, le=20)
    document_id: int | None = Field(default=None, ge=1)
    category: str | None = Field(default=None, max_length=50)


class SearchResult(BaseModel):
    document_id: int
    filename: str
    chunk_index: int
    snippet: str
    score: float
    category: str
    file_type: str
    highlights: list[str] = Field(default_factory=list)
    match_type: str
    relevance_label: str


class SearchResponse(BaseModel):
    results: list[SearchResult]

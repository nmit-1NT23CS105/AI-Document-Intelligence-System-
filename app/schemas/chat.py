from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    document_id: int | None = Field(default=None, ge=1)
    limit: int = Field(default=4, ge=1, le=10)


class ChatCitation(BaseModel):
    document_id: int
    filename: str
    chunk_index: int


class ChatResponse(BaseModel):
    answer: str
    citations: list[ChatCitation]

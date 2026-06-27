from __future__ import annotations

from pydantic import BaseModel, Field


class SummaryRequest(BaseModel):
    document_id: int = Field(ge=1)
    max_key_points: int = Field(default=5, ge=1, le=10)


class SummaryResponse(BaseModel):
    document_id: int
    filename: str
    short_summary: str
    key_points: list[str]

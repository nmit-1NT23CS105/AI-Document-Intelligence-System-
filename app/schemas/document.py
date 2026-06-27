from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    filepath: str
    file_type: str
    category: str
    number_of_pages: int | None
    upload_date: datetime


class DocumentDetail(DocumentSummary):
    extracted_text: str


class DocumentMetadata(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    file_type: str
    upload_date: datetime
    number_of_pages: int | None
    category: str

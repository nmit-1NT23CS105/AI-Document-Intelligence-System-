from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai.summarization import summarize_text
from app.core.config import get_settings
from app.database.models import User
from app.services.document_service import get_user_document


def summarize_document(
    db: Session,
    user: User,
    document_id: int,
    max_key_points: int,
) -> tuple[str, str, list[str]]:
    document = get_user_document(db=db, user=user, document_id=document_id)
    extracted_text = ""
    if document.text_content:
        extracted_text = document.text_content.extracted_text

    settings = get_settings()
    short_summary, key_points = summarize_text(
        extracted_text,
        summary_sentence_count=settings.summary_sentence_count,
        max_key_points=max_key_points,
    )
    return document.filename, short_summary, key_points

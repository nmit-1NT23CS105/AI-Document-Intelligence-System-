from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai.llm import get_llm_client, parse_llm_summary
from app.ai.summarization import summarize_text
from app.core.config import get_settings
from app.database.models import User
from app.services.document_service import get_user_document


def _llm_summarize_document(
    filename: str,
    extracted_text: str,
    max_key_points: int,
) -> tuple[str, list[str]] | None:
    llm_client = get_llm_client()
    if llm_client is None or not extracted_text.strip():
        return None

    system_prompt = (
        "You summarize documents for an AI document intelligence system. "
        "Use only the provided document text. Return valid JSON only with "
        "keys short_summary and key_points."
    )
    user_prompt = (
        f"Document filename: {filename}\n\n"
        f"Document text:\n{extracted_text[:12000]}\n\n"
        "Return JSON in this exact shape:\n"
        '{"short_summary":"one concise paragraph","key_points":["point 1","point 2"]}\n'
        f"Include at most {max_key_points} key points."
    )

    try:
        raw_summary = llm_client.generate_text(system_prompt, user_prompt)
    except Exception:
        return None

    return parse_llm_summary(raw_summary, max_key_points=max_key_points)


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

    llm_summary = _llm_summarize_document(
        filename=document.filename,
        extracted_text=extracted_text,
        max_key_points=max_key_points,
    )
    if llm_summary is not None:
        short_summary, key_points = llm_summary
        return document.filename, short_summary, key_points

    settings = get_settings()
    short_summary, key_points = summarize_text(
        extracted_text,
        summary_sentence_count=settings.summary_sentence_count,
        max_key_points=max_key_points,
    )
    return document.filename, short_summary, key_points

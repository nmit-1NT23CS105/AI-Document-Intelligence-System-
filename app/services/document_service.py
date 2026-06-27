from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.ai.classification import get_document_classifier
from app.database.models import Document, DocumentText, User
from app.services.search_service import index_document_text, remove_document_from_index
from app.services.text_extraction_service import TextExtractionError, extract_text

SUPPORTED_EXTENSIONS = {".pdf": "pdf", ".docx": "docx"}


def _safe_filename(filename: str) -> str:
    original_name = Path(filename).name
    sanitized = re.sub(r"[^A-Za-z0-9._-]", "_", original_name)
    return sanitized or "document"


def _file_type_for(filename: str) -> str:
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF and DOCX files are supported",
        )
    return SUPPORTED_EXTENSIONS[extension]


def _ensure_upload_size(content: bytes, max_size_bytes: int) -> None:
    if len(content) > max_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="File exceeds the maximum allowed size",
        )


async def create_document_from_upload(
    db: Session,
    user: User,
    upload: UploadFile,
    upload_dir: str,
    max_size_bytes: int,
) -> Document:
    filename = upload.filename or ""
    file_type = _file_type_for(filename)
    content = await upload.read()
    _ensure_upload_size(content=content, max_size_bytes=max_size_bytes)

    directory = Path(upload_dir)
    directory.mkdir(parents=True, exist_ok=True)
    safe_name = _safe_filename(filename)
    file_path = directory / f"{uuid4().hex}_{safe_name}"
    file_path.write_bytes(content)

    try:
        extracted_text, page_count = extract_text(file_path=file_path, file_type=file_type)
    except TextExtractionError as exc:
        file_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        file_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not extract text from document",
        ) from exc

    document = Document(
        user_id=user.id,
        filename=safe_name,
        filepath=str(file_path),
        file_type=file_type,
        category=get_document_classifier().classify(extracted_text),
        number_of_pages=page_count,
        text_content=DocumentText(extracted_text=extracted_text),
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    index_document_text(db=db, document=document, extracted_text=extracted_text)
    db.refresh(document)
    return document


def list_user_documents(db: Session, user: User) -> list[Document]:
    return (
        db.query(Document)
        .filter(Document.user_id == user.id)
        .order_by(Document.upload_date.desc(), Document.id.desc())
        .all()
    )


def get_user_document(db: Session, user: User, document_id: int) -> Document:
    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == user.id)
        .first()
    )
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    return document


def delete_user_document(db: Session, user: User, document_id: int) -> None:
    document = get_user_document(db=db, user=user, document_id=document_id)
    remove_document_from_index(document_id=document.id)
    Path(document.filepath).unlink(missing_ok=True)
    db.delete(document)
    db.commit()

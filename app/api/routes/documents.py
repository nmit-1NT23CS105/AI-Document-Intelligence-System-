from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.core.config import get_settings
from app.database.models import User
from app.database.session import get_db
from app.schemas.document import DocumentDetail, DocumentMetadata, DocumentSummary
from app.services.document_service import (
    create_document_from_upload,
    delete_user_document,
    get_user_document,
    list_user_documents,
)

router = APIRouter(tags=["Documents"])


def _detail_response(document) -> DocumentDetail:
    extracted_text = ""
    if document.text_content:
        extracted_text = document.text_content.extracted_text
    summary = DocumentSummary.model_validate(document).model_dump()
    return DocumentDetail(**summary, extracted_text=extracted_text)


@router.post(
    "/upload",
    response_model=DocumentSummary,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    file: UploadFile = File(...),
) -> DocumentSummary:
    settings = get_settings()
    return await create_document_from_upload(
        db=db,
        user=current_user,
        upload=file,
        upload_dir=settings.upload_dir,
        max_size_bytes=settings.max_upload_size_bytes,
    )


@router.get("/documents", response_model=list[DocumentSummary])
def documents(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[DocumentSummary]:
    return list_user_documents(db=db, user=current_user)


@router.get("/document/{document_id}", response_model=DocumentDetail)
def document_detail(
    document_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> DocumentDetail:
    document = get_user_document(db=db, user=current_user, document_id=document_id)
    return _detail_response(document)


@router.delete("/document/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    delete_user_document(db=db, user=current_user, document_id=document_id)


@router.get("/metadata/{document_id}", response_model=DocumentMetadata)
def document_metadata(
    document_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> DocumentMetadata:
    return get_user_document(db=db, user=current_user, document_id=document_id)

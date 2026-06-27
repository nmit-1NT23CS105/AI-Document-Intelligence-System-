from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database.models import User
from app.database.session import get_db
from app.schemas.summary import SummaryRequest, SummaryResponse
from app.services.summary_service import summarize_document

router = APIRouter(tags=["AI Summarization"])


@router.post("/summarize", response_model=SummaryResponse)
def summarize(
    payload: SummaryRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> SummaryResponse:
    filename, short_summary, key_points = summarize_document(
        db=db,
        user=current_user,
        document_id=payload.document_id,
        max_key_points=payload.max_key_points,
    )
    return SummaryResponse(
        document_id=payload.document_id,
        filename=filename,
        short_summary=short_summary,
        key_points=key_points,
    )

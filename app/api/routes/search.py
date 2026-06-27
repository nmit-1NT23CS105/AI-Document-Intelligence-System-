from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database.models import User
from app.database.session import get_db
from app.schemas.search import SearchRequest, SearchResponse, SearchResult
from app.services.search_service import search_documents

router = APIRouter(tags=["Semantic Search"])


@router.post("/search", response_model=SearchResponse)
def semantic_search(
    payload: SearchRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> SearchResponse:
    results = search_documents(
        db=db,
        user=current_user,
        query=payload.query,
        limit=payload.limit,
    )
    return SearchResponse(
        results=[
            SearchResult(
                document_id=result.document_id,
                filename=result.filename,
                chunk_index=result.chunk_index,
                snippet=result.snippet,
                score=result.score,
            )
            for result in results
        ]
    )

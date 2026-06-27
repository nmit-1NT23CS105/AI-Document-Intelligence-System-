from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.session import get_db

router = APIRouter(tags=["Health"])


@router.get("/health")
def health(db: Annotated[Session, Depends(get_db)]) -> dict[str, str]:
    settings = get_settings()
    db.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "app_name": settings.app_name,
        "version": settings.app_version,
        "database": "ok",
    }

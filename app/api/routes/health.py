from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database.session import get_db
from app.core.config import settings

router = APIRouter(tags=["Health & Status"])


@router.get("/health", summary="Service Health Check")
def health_check(db: Session = Depends(get_db)):
    """Health check endpoint probing application status and database connectivity."""
    db_status = "healthy"
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        db_status = f"unhealthy: {str(exc)}"

    return {
        "status": "online" if db_status == "healthy" else "degraded",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "database": db_status,
        "whatsapp_provider": settings.WHATSAPP_PROVIDER,
    }


@router.get("/", summary="Root Metadata")
def root_status():
    return {
        "status": "running",
        "clinic_name": settings.CLINIC_NAME,
        "docs_url": "/docs",
        "version": settings.APP_VERSION,
    }

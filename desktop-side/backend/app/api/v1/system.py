"""Non-secret system configuration, health and synchronization control."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import DEFAULT_SECRET_KEY, settings
from app.core.database import get_db
from app.core.security import get_current_user, require_management
from app.models.user import User
from app.services import ocr_service
from app.services.audit import record_audit
from app.services.cloud_sync import push_pending, sync_state
from app.services.document_classification import type_catalog

router = APIRouter(prefix="/system", tags=["System"])


def _opencv_status() -> dict:
    try:
        import cv2

        return {"available": True, "version": cv2.__version__}
    except Exception as exc:  # pragma: no cover
        return {"available": False, "reason": str(exc)}


@router.get("/settings")
def get_system_settings(db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    """Configuration visible to signed-in users. Secrets are never returned."""
    url = make_url(settings.DATABASE_URL)
    try:
        migration = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
    except Exception:
        db.rollback()
        migration = None
    return {
        "application": {"name": settings.APP_NAME, "api_version": "v1"},
        "database": {"dialect": url.get_backend_name(), "host": url.host, "port": url.port,
                     "name": url.database, "migration_revision": migration},
        "security": {"token_lifetime_minutes": settings.ACCESS_TOKEN_EXPIRE_MINUTES,
                     "secret_key_configured": settings.SECRET_KEY != DEFAULT_SECRET_KEY,
                     "cors_origins": settings.cors_origins},
        "cloud": {"supabase_configured": settings.cloud_configured,
                  "cloud_sync_enabled": settings.CLOUD_SYNC_ENABLED},
        "storage": {
            "backend": settings.storage_backend,
            "documents_bucket": (
                settings.SUPABASE_DOCUMENTS_BUCKET if settings.storage_backend == "supabase" else None
            ),
            "max_upload_mb": settings.MAX_UPLOAD_MB,
            "accepted_formats": ["PDF", "DOCX", "PNG", "JPEG", "TIFF", "BMP", "WEBP"],
        },
        "processing": {
            "ocr": ocr_service.engine_status(),
            "ocr_min_text_chars_per_page": settings.OCR_MIN_TEXT_CHARS,
            "opencv": _opencv_status(),
            "document_types": [item["code"] for item in type_catalog()],
        },
        "forecasting": {"minimum_complete_months": settings.FORECAST_MIN_MONTHS},
    }


@router.get("/sync")
def get_sync_status(db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    return sync_state(db)


@router.post("/sync/push")
def push_sync(db: Session = Depends(get_db), user: User = Depends(require_management)):
    report = push_pending(db)
    failed = any(table["failed"] for table in report.get("tables", {}).values())
    record_audit(db, "CLOUD_PUSH", actor=user, entity_type="sync",
                 result="FAILED" if failed else "SUCCESS", details=report)
    db.commit()
    return report

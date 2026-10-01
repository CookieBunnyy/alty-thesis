from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_SECRET_KEY = "change-this-secret-key"


class Settings(BaseSettings):
    APP_NAME: str = "Abellar Realty Management System"
    # No credential default: DATABASE_URL must come from the environment/.env.
    DATABASE_URL: str = "postgresql+psycopg://localhost:5432/abellar"
    SECRET_KEY: str = DEFAULT_SECRET_KEY
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    ALGORITHM: str = "HS256"

    # Supabase (backend only — never shipped to desktop or web clients).
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_DOCUMENTS_BUCKET: str = "documents"
    SUPABASE_MEDIA_BUCKET: str = "documents"
    # Push local document-derived records to Supabase after each change.
    CLOUD_SYNC_ENABLED: bool = True

    # File storage: "supabase", "local", or "auto" (supabase when configured).
    DOCUMENT_STORAGE_BACKEND: str = "auto"
    DOCUMENT_STORAGE_DIR: str = str(BACKEND_DIR / "storage")
    MAX_UPLOAD_MB: int = 25

    # OCR: "auto" (RapidOCR, then Tesseract), "rapidocr", "tesseract", "none".
    OCR_ENGINE: str = "auto"
    # A PDF page with fewer extractable characters than this is treated as scanned.
    OCR_MIN_TEXT_CHARS: int = 40

    # Forecasting requires at least this many monthly observations.
    FORECAST_MIN_MONTHS: int = 6

    # Comma-separated origins allowed to call the API from a browser.
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    # Public website transaction submissions per client IP per hour.
    PUBLIC_SUBMISSIONS_PER_HOUR: int = 20

    # Only used to create the first administrator on an empty users table.
    INITIAL_ADMIN_USERNAME: str = "admin"
    INITIAL_ADMIN_PASSWORD: str = ""

    model_config = SettingsConfigDict(env_file=str(BACKEND_DIR / ".env"), extra="ignore")

    @property
    def cloud_configured(self) -> bool:
        return bool(self.SUPABASE_URL and self.SUPABASE_SERVICE_ROLE_KEY)

    @property
    def storage_backend(self) -> str:
        backend = self.DOCUMENT_STORAGE_BACKEND.strip().casefold()
        if backend == "auto":
            return "supabase" if self.cloud_configured else "local"
        return backend

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

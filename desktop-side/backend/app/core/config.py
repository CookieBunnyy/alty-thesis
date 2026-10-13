import os
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
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
    # Used for agents without a recorded commission rate (total commission ÷ total sales).
    DEFAULT_COMMISSION_RATE: float = 0.03

    # Comma-separated origins allowed to call the API from a browser.
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    # Optional pattern for origins that change per deploy, e.g. every Vercel
    # deployment/preview URL of one project:
    # ^https://alty-thesis(-[a-z0-9]+)*-cookiebunnyys-projects\.vercel\.app$
    CORS_ORIGIN_REGEX: str = ""
    # Public website transaction submissions per client IP per hour.
    PUBLIC_SUBMISSIONS_PER_HOUR: int = 20

    # Road routing for the website map: "osrm", "valhalla" or "none".
    # OSRM (the project's existing provider) has car, bicycle and foot
    # profiles but no motorcycle profile; Valhalla also has motorcycle.
    ROUTING_PROVIDER: str = "osrm"
    # One OSRM server per profile (router.project-osrm.org ignores the
    # profile and always routes by car, so it is not used for bike/foot).
    OSRM_DRIVING_URL: str = "https://routing.openstreetmap.de/routed-car"
    OSRM_BICYCLE_URL: str = "https://routing.openstreetmap.de/routed-bike"
    OSRM_WALKING_URL: str = "https://routing.openstreetmap.de/routed-foot"
    VALHALLA_URL: str = "https://valhalla1.openstreetmap.de"
    ROUTING_TIMEOUT_SECONDS: float = 8.0
    ROUTE_CACHE_SECONDS: int = 1800
    # Live-traffic routes (ROUTING_PROVIDER=tomtom) go stale quickly.
    LIVE_ROUTE_CACHE_SECONDS: int = 120
    TOMTOM_API_URL: str = "https://api.tomtom.com"
    # Live traffic heat map: "none" or "tomtom" (needs TOMTOM_API_KEY; tiles
    # are proxied by the backend so the key never reaches the browser).
    # For traffic-aware travel times also set ROUTING_PROVIDER=tomtom.
    TRAFFIC_PROVIDER: str = "none"
    TOMTOM_API_KEY: str = ""
    # Place search for the workplace picker (Nominatim usage policy: an
    # identifying User-Agent and at most one request per second).
    GEOCODER_URL: str = "https://nominatim.openstreetmap.org"
    GEOCODER_USER_AGENT: str = "AltyAbellarRealty/1.0"
    GEOCODER_COUNTRY_CODES: str = "ph"
    # Public map requests (routes, place search) per client IP per minute.
    MAP_REQUESTS_PER_MINUTE: int = 60

    # ---- Staff sign-in protection -------------------------------------------
    # Where the visitor's IP comes from. Behind Render (which runs behind
    # Cloudflare) set CLIENT_IP_HEADER=cf-connecting-ip: Cloudflare sets it
    # itself, whereas X-Forwarded-For keeps whatever the visitor sent. With
    # CLIENT_IP_HEADER empty, TRUSTED_PROXY_HOPS>0 reads X-Forwarded-For from
    # the right (the entries added by that many trusted proxies); 0 uses the
    # direct connection (local development).
    CLIENT_IP_HEADER: str = ""
    TRUSTED_PROXY_HOPS: int = 0
    # Failed sign-ins per account inside the window -> temporary cooldowns
    # ("failures:seconds", progressive). Never a permanent lockout.
    LOGIN_FAILURE_WINDOW_MINUTES: int = 30
    LOGIN_COOLDOWN_STEPS: str = "5:60,10:300,15:900"
    LOGIN_MAX_ATTEMPTS_PER_IP: int = 60          # per 15 minutes
    # The security check (Cloudflare Turnstile) is required after this many
    # failures for the account, or 2x this many from one IP.
    LOGIN_CAPTCHA_AFTER_FAILURES: int = 3
    # Cloudflare Turnstile. The site key is public (sent to the browser); the
    # secret key stays on the server. Both empty = no security check.
    TURNSTILE_SITE_KEY: str = ""
    TURNSTILE_SECRET_KEY: str = ""

    # ---- Staff password recovery ---------------------------------------------
    # Reset links are built from this trusted address (the Management System's
    # site, e.g. https://alty-msa.vercel.app), never from the request's Host.
    # Empty = password recovery is switched off.
    STAFF_APP_URL: str = ""
    PASSWORD_RESET_TTL_MINUTES: int = 20         # clamped to 15-30
    PASSWORD_RESET_PER_EMAIL_PER_HOUR: int = 3
    PASSWORD_RESET_MIN_EMAIL_INTERVAL_SECONDS: int = 120
    PASSWORD_RESET_PER_IP_PER_HOUR: int = 10

    # ---- Email (password reset and password-changed notices) -----------------
    # "brevo" or "resend" (HTTPS APIs), "smtp", or "none". Render's free plan
    # blocks outbound SMTP ports, so use an HTTPS provider there.
    EMAIL_PROVIDER: str = "none"
    EMAIL_FROM: str = ""
    EMAIL_FROM_NAME: str = "Abellar Realty"
    BREVO_API_KEY: str = ""
    RESEND_API_KEY: str = ""
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_TIMEOUT_SECONDS: float = 10.0

    # Only used to create the first administrator on an empty users table.
    INITIAL_ADMIN_USERNAME: str = "admin"
    INITIAL_ADMIN_PASSWORD: str = ""

    model_config = SettingsConfigDict(env_file=str(BACKEND_DIR / ".env"), extra="ignore")

    @field_validator("DATABASE_URL")
    @classmethod
    def use_psycopg_driver(cls, value: str) -> str:
        """Hosts (Render, Supabase) hand out postgres:// or postgresql:// URLs;
        SQLAlchemy needs the psycopg driver named explicitly."""
        # A pasted URL often carries a trailing newline/space, which would
        # become part of the database name ("postgres\n" does not exist).
        value = value.strip()
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                value = "postgresql+psycopg://" + value[len(prefix):]
                break
        # On a host (Render sets RENDER=true) there is no local Postgres: say
        # so plainly instead of failing later with "connection refused".
        if os.environ.get("RENDER") and any(local in value for local in ("@localhost", "//localhost", "127.0.0.1")):
            raise ValueError(
                "DATABASE_URL points at localhost, which doesn't exist on Render. Set DATABASE_URL in the "
                "service's Environment tab to a cloud PostgreSQL URL (Render PostgreSQL 'Internal Database URL' "
                "or a Supabase 'Session pooler' connection string)."
            )
        return value

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
    def captcha_enabled(self) -> bool:
        return bool(self.TURNSTILE_SITE_KEY.strip() and self.TURNSTILE_SECRET_KEY.strip())

    @property
    def password_reset_enabled(self) -> bool:
        return bool(self.STAFF_APP_URL.strip() and self.EMAIL_PROVIDER.strip().casefold() != "none")

    @property
    def password_reset_ttl_minutes(self) -> int:
        return min(30, max(15, self.PASSWORD_RESET_TTL_MINUTES))

    @property
    def login_cooldown_steps(self) -> list[tuple[int, int]]:
        """[(failures, seconds)] from LOGIN_COOLDOWN_STEPS, smallest first."""
        steps = []
        for part in self.LOGIN_COOLDOWN_STEPS.split(","):
            failures, _, seconds = part.strip().partition(":")
            if failures.strip().isdigit() and seconds.strip().isdigit():
                steps.append((int(failures), int(seconds)))
        return sorted(steps)

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

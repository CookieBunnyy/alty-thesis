"""Backend-only Supabase client.

The service-role key never leaves the server. The client is created lazily
so the API still starts (in local-only mode) when Supabase is not configured.
"""

from __future__ import annotations

from typing import Any

from app.core.config import settings


class SupabaseNotConfigured(RuntimeError):
    pass


class _LazySupabase:
    def __init__(self) -> None:
        self._client = None

    def _get(self):
        if self._client is None:
            if not settings.cloud_configured:
                raise SupabaseNotConfigured(
                    "Supabase is not configured on the server "
                    "(SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY)."
                )
            from supabase import create_client

            self._client = create_client(
                settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY
            )
        return self._client

    def __getattr__(self, name: str) -> Any:
        return getattr(self._get(), name)


supabase = _LazySupabase()

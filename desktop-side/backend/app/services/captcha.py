"""Cloudflare Turnstile verification (server side; the secret never leaves it)."""

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger("alty.captcha")
VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def verify_turnstile(token: str | None, ip: str | None = None) -> bool:
    """True when Cloudflare accepts ``token``. A missing token, a refusal or an
    unreachable Cloudflare all count as a failed check."""
    if not token or len(token) > 2048:
        return False
    data = {"secret": settings.TURNSTILE_SECRET_KEY, "response": token}
    if ip and ip != "unknown":
        data["remoteip"] = ip
    try:
        response = httpx.post(VERIFY_URL, data=data, timeout=8.0)
        return bool(response.json().get("success"))
    except (httpx.HTTPError, ValueError):
        logger.warning("Turnstile verification failed: Cloudflare unreachable or invalid reply")
        return False

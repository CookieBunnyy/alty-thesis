"""The visitor's IP address, for rate limits and audit records.

Never trust the left of X-Forwarded-For: a visitor can send that header
themselves, and proxies only append to it. Choose one source:

* CLIENT_IP_HEADER (e.g. ``cf-connecting-ip``): a header the edge proxy sets
  itself, overwriting anything the visitor sent. Render runs behind
  Cloudflare, which sets CF-Connecting-IP.
* TRUSTED_PROXY_HOPS = N: the Nth entry of X-Forwarded-For counted from the
  right, i.e. the address the outermost of N trusted proxies saw.
* neither: the direct connection (local development).
"""

from ipaddress import ip_address

from fastapi import Request

from app.core.config import settings


def _valid(value: str | None) -> str | None:
    value = (value or "").strip()
    try:
        return str(ip_address(value)) if value else None
    except ValueError:
        return None


def client_ip(request: Request) -> str:
    header = settings.CLIENT_IP_HEADER.strip()
    if header:
        found = _valid(request.headers.get(header))
        if found:
            return found
    hops = settings.TRUSTED_PROXY_HOPS
    if hops > 0:
        entries = [entry.strip() for entry in request.headers.get("x-forwarded-for", "").split(",") if entry.strip()]
        if len(entries) >= hops:
            found = _valid(entries[-hops])
            if found:
                return found
    peer = request.scope.get("client")
    return (peer[0] if peer else None) or "unknown"

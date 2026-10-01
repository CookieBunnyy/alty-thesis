"""Live traffic layer for the website map.

Only real provider data is shown. With ``TRAFFIC_PROVIDER=none`` (the
default) the API reports that live traffic is unavailable and the website
says so; it never draws a substitute overlay.

``tomtom`` serves TomTom Traffic Flow raster tiles (relative speed: green =
free flow … red = congested) through the backend, so ``TOMTOM_API_KEY`` is
never sent to the browser.
"""

from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod

import httpx

from app.core.config import settings


class TrafficUnavailable(Exception):
    pass


class TrafficProvider(ABC):
    name = "none"
    attribution = ""
    # Colour key for the overlay, low -> high congestion.
    legend: list[dict] = []

    @property
    @abstractmethod
    def available(self) -> bool: ...

    @property
    def message(self) -> str:
        return "Live traffic data is available." if self.available else \
            "Live traffic data is not available: no traffic provider is configured."

    @abstractmethod
    def fetch_tile(self, z: int, x: int, y: int, theme: str = "light") -> bytes: ...

    def status(self) -> dict:
        return {"available": self.available, "provider": self.name if self.available else None,
                "message": self.message, "legend": self.legend if self.available else [],
                "attribution": self.attribution if self.available else ""}


class NoTrafficProvider(TrafficProvider):
    @property
    def available(self) -> bool:
        return False

    def fetch_tile(self, z, x, y, theme="light"):
        raise TrafficUnavailable()


class TomTomTrafficProvider(TrafficProvider):
    name = "tomtom"
    attribution = "Traffic © TomTom"
    # Colour key of TomTom's "relative0" flow style (speed relative to free flow).
    legend = [
        {"level": "low", "label": "Free flow", "color": "#3BB54A"},
        {"level": "medium", "label": "Slow", "color": "#F5A623"},
        {"level": "high", "label": "Congested", "color": "#D0021B"},
        {"level": "closed", "label": "Stopped / closed", "color": "#7A0B0B"},
    ]
    TILE_PATH = "/traffic/map/4/tile/flow/{style}/{z}/{x}/{y}.png"
    STYLES = {"light": "relative0", "dark": "relative0-dark"}
    TILE_SECONDS = 120  # flow tiles refresh every couple of minutes

    def __init__(self, api_key: str, client: httpx.Client | None = None) -> None:
        self.api_key = api_key
        self.client = client or httpx.Client(timeout=settings.ROUTING_TIMEOUT_SECONDS)
        self._tiles: dict[tuple[str, int, int, int], tuple[float, bytes]] = {}
        self._lock = threading.Lock()

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def fetch_tile(self, z, x, y, theme="light"):
        if not self.available:
            raise TrafficUnavailable()
        style = self.STYLES.get(theme, self.STYLES["light"])
        key = (style, z, x, y)
        with self._lock:
            hit = self._tiles.get(key)
            if hit and hit[0] > time.monotonic():
                return hit[1]
        try:
            response = self.client.get(settings.TOMTOM_API_URL.rstrip("/") + self.TILE_PATH.format(style=style, z=z, x=x, y=y),
                                       params={"key": self.api_key, "tileSize": 256})
        except httpx.HTTPError as exc:
            raise TrafficUnavailable() from exc
        if response.status_code != 200 or not response.headers.get("content-type", "").startswith("image/"):
            raise TrafficUnavailable()
        with self._lock:
            if len(self._tiles) > 3000:
                self._tiles.clear()
            self._tiles[key] = (time.monotonic() + self.TILE_SECONDS, response.content)
        return response.content


_provider: TrafficProvider | None = None


def get_traffic_provider() -> TrafficProvider:
    global _provider
    if _provider is None:
        if settings.TRAFFIC_PROVIDER.strip().casefold() == "tomtom":
            _provider = TomTomTrafficProvider(settings.TOMTOM_API_KEY)
        else:
            _provider = NoTrafficProvider()
    return _provider


def set_traffic_provider(provider: TrafficProvider | None) -> None:
    global _provider
    _provider = provider

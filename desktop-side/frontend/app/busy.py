"""Keep the window responsive while the API works, and say so on screen.

Every API call goes through ``ApiClient`` -> ``ResponsiveHttpClient``. On the
GUI thread the HTTP request runs on a worker thread while Qt keeps painting
and running timers (so loading animations move), but *user input* is held
back until the request finishes, so a click can't start a second action
halfway through the first. ``busy_tracker()`` reports when work is in
progress, and with which label ("Loading Agents…"), for the indicators in
``app.views.loading``.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, wait
from contextlib import contextmanager
from typing import Any, Callable, Iterator, TypeVar

from PyQt6.QtCore import QEventLoop, QObject, QThread, pyqtSignal
from PyQt6.QtWidgets import QApplication

T = TypeVar("T")
DEFAULT_LABEL = "Loading…"


class BusyTracker(QObject):
    """Counts work in progress; ``changed(busy, label)`` on every change."""

    changed = pyqtSignal(bool, str)

    def __init__(self) -> None:
        super().__init__()
        self._count = 0
        self._labels: list[tuple[str, bool]] = []

    @property
    def busy(self) -> bool:
        return self._count > 0

    @property
    def label(self) -> str:
        return self._labels[-1][0] if self._labels else DEFAULT_LABEL

    @property
    def show_overlay(self) -> bool:
        """False for background work (status refresh) that shouldn't dim the page."""
        return not (self._labels and self._labels[-1][1])

    def begin(self) -> None:
        self._count += 1
        if self._count == 1:
            self.changed.emit(True, self.label)

    def end(self) -> None:
        self._count = max(0, self._count - 1)
        if self._count == 0:
            self.changed.emit(False, self.label)

    @contextmanager
    def labelled(self, label: str, quiet: bool = False) -> Iterator[None]:
        """Describe the work started inside this block ("Loading Agents…").
        ``quiet`` work shows the progress bar only, never the page overlay."""
        self._labels.append((label, quiet))
        if self.busy:
            self.changed.emit(True, label)
        try:
            yield
        finally:
            self._labels.pop()


_tracker: BusyTracker | None = None
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="alty-api")


def busy_tracker() -> BusyTracker:
    global _tracker
    if _tracker is None:
        _tracker = BusyTracker()
    return _tracker


def _on_gui_thread() -> bool:
    app = QApplication.instance()
    return app is not None and QThread.currentThread() is app.thread()


def run_responsive(work: Callable[[], T]) -> T:
    """Run ``work`` without freezing the window (GUI thread only; elsewhere
    it simply runs). Exceptions are re-raised to the caller unchanged."""
    if not _on_gui_thread():
        return work()
    tracker = busy_tracker()
    tracker.begin()
    try:
        future = _executor.submit(work)
        while not future.done():
            QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents, 25)
            wait([future], timeout=0.012)
        return future.result()
    finally:
        tracker.end()


class ResponsiveHttpClient:
    """``httpx.Client`` whose requests use ``run_responsive``."""

    _WRAPPED = {"request", "get", "post", "put", "patch", "delete"}

    def __init__(self, client: Any) -> None:
        self._client = client

    def __getattr__(self, name: str) -> Any:
        attribute = getattr(self._client, name)
        if name not in self._WRAPPED or not callable(attribute):
            return attribute

        def call(*args: Any, **kwargs: Any) -> Any:
            return run_responsive(lambda: attribute(*args, **kwargs))

        return call

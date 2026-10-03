"""Loading indicators driven by ``app.busy.busy_tracker()``.

* ``Spinner``        – rotating arc (theme accent).
* ``BusyBar``        – slim indeterminate bar under the header; appears after
  a short delay so instant responses don't flicker.
* ``LoadingOverlay`` – dims a widget (the page area) with "Loading Agents…"
  when the work takes a little longer.
"""

from __future__ import annotations

from PyQt6.QtCore import QEvent, QObject, QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QFrame, QGraphicsBlurEffect, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from app.busy import busy_tracker
from app.theme import TOKENS as T

FRAME_MS = 16


class Spinner(QWidget):
    def __init__(self, size: int = 28, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.setInterval(FRAME_MS)
        self._timer.timeout.connect(self._tick)

    def showEvent(self, event) -> None:
        self._timer.start()
        super().showEvent(event)

    def hideEvent(self, event) -> None:
        self._timer.stop()
        super().hideEvent(event)

    def _tick(self) -> None:
        self._angle = (self._angle + 6) % 360
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width = max(2.5, self.width() / 9)
        rect = QRectF(width, width, self.width() - 2 * width, self.height() - 2 * width)
        painter.setPen(QPen(QColor(T["border_strong"]), width, cap=Qt.PenCapStyle.RoundCap))
        painter.drawEllipse(rect)
        painter.setPen(QPen(QColor(T["accent"]), width, cap=Qt.PenCapStyle.RoundCap))
        painter.drawArc(rect, -self._angle * 16, 100 * 16)


class BusyBar(QWidget):
    """Indeterminate progress bar (a lime segment sliding across)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(3)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._offset = 0.0
        self._active = False
        self._timer = QTimer(self)
        self._timer.setInterval(FRAME_MS)
        self._timer.timeout.connect(self._tick)

    def set_active(self, active: bool) -> None:
        self._active = active
        self._timer.start() if active else self._timer.stop()
        self.update()

    def _tick(self) -> None:
        self._offset = (self._offset + 0.012) % 1.4
        self.update()

    def paintEvent(self, _event) -> None:
        if not self._active:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        track = QColor(T["accent"])
        track.setAlpha(45)
        painter.fillRect(self.rect(), track)
        segment = self.width() * 0.4
        x = (self._offset - 0.4) * self.width()
        painter.setBrush(QColor(T["accent"]))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(QRectF(x, 0, segment, self.height()), 1.5, 1.5)


class LoadingOverlay(QWidget):
    """Covers ``target`` with a dim layer and a centered "Loading…" card.
    While shown, ``blur`` (the page content under it) is blurred."""

    BLUR_RADIUS = 9

    def __init__(self, target: QWidget, blur: QWidget | None = None) -> None:
        super().__init__(target)
        self.target = target
        self.blur = blur
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName("loadingOverlay")
        dim = QColor(T["bg"])
        self.setStyleSheet(
            f"/*alty-raw*/ QWidget#loadingOverlay {{ background: rgba({dim.red()},{dim.green()},{dim.blue()},90); }}"
            f" QFrame#loadingCard {{ background: {T['card']}; border: 1px solid {T['border']}; border-radius: 14px; }}"
            f" QLabel#loadingText {{ color: {T['text']}; font-size: 13px; font-weight: 600; background: transparent; }}"
            f" QLabel#loadingHint {{ color: {T['text_faint']}; font-size: 11px; background: transparent; }}"
        )
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card = QFrame()
        card.setObjectName("loadingCard")
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(20, 16, 24, 16)
        card_layout.setSpacing(14)
        self.spinner = Spinner(30)
        card_layout.addWidget(self.spinner)
        texts = QVBoxLayout()
        texts.setSpacing(2)
        self.text = QLabel("Loading…")
        self.text.setObjectName("loadingText")
        hint = QLabel("Fetching the latest data from the server")
        hint.setObjectName("loadingHint")
        texts.addWidget(self.text)
        texts.addWidget(hint)
        card_layout.addLayout(texts)
        layout.addWidget(card)
        target.installEventFilter(self)
        self.hide()

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if obj is self.target and event.type() in (QEvent.Type.Resize, QEvent.Type.Show):
            self.setGeometry(self.target.rect())
        return False

    def show_with(self, label: str) -> None:
        self.text.setText(label)
        self.setGeometry(self.target.rect())
        if self.blur is not None and self.blur.graphicsEffect() is None:
            effect = QGraphicsBlurEffect(self.blur)
            effect.setBlurRadius(self.BLUR_RADIUS)
            effect.setBlurHints(QGraphicsBlurEffect.BlurHint.PerformanceHint)
            self.blur.setGraphicsEffect(effect)
        self.raise_()
        self.show()

    def hideEvent(self, event) -> None:
        if self.blur is not None and isinstance(self.blur.graphicsEffect(), QGraphicsBlurEffect):
            self.blur.setGraphicsEffect(None)  # deletes the effect: content is sharp again
        super().hideEvent(event)


class BusyIndicators(QObject):
    """Connects the busy tracker to a bar and an overlay, with delays so
    quick requests show nothing and slower ones show progress."""

    BAR_DELAY_MS = 120
    OVERLAY_DELAY_MS = 350

    def __init__(self, bar: BusyBar, overlay: LoadingOverlay | None, parent: QObject) -> None:
        super().__init__(parent)
        self.bar, self.overlay = bar, overlay
        self._label = "Loading…"
        self._bar_timer = self._single_shot(self.BAR_DELAY_MS, lambda: self.bar.set_active(True))
        self._overlay_timer = self._single_shot(
            self.OVERLAY_DELAY_MS, lambda: self.overlay and self.overlay.show_with(self._label))
        busy_tracker().changed.connect(self._changed)

    def _single_shot(self, delay: int, slot) -> QTimer:
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.setInterval(delay)
        timer.timeout.connect(slot)
        return timer

    def _changed(self, busy: bool, label: str) -> None:
        self._label = label
        if busy:
            if self.overlay is not None and self.overlay.isVisible():
                self.overlay.text.setText(label)
            if not self._bar_timer.isActive() and not self.bar._active:
                self._bar_timer.start()
            if self.overlay is not None and busy_tracker().show_overlay                     and not self._overlay_timer.isActive() and not self.overlay.isVisible():
                self._overlay_timer.start()
        else:
            self._bar_timer.stop()
            self._overlay_timer.stop()
            self.bar.set_active(False)
            if self.overlay is not None:
                self.overlay.hide()

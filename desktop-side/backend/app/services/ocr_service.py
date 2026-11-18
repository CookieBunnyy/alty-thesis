"""Replaceable OCR layer.

Engines are tried in order (``OCR_ENGINE=auto``): RapidOCR (ONNX, pip-only)
then Tesseract (requires the system binary). Add another engine by
implementing :class:`OcrEngine` and registering it in ``_ENGINES``.

Memory: reading a photo is the most memory-hungry thing the API does. With
RapidOCR's defaults one ~280 KB phone photo peaked at ~550 MB, more than
Render's free plan gives the whole app, so the server was killed mid-upload.
Images are therefore shrunk to ``OCR_MAX_SIDE`` (1280 px: ~270 MB peak, same
text read), the detector works at up to 960 px, the text-rotation classifier
is off, one thread is used, only one document is read at a time, and freed
memory is handed back to the system after each read.
"""

from __future__ import annotations

import ctypes
import gc
import logging
import shutil
import sys
import threading
from functools import lru_cache
from typing import Protocol

import numpy as np

from app.core.config import settings

logger = logging.getLogger(__name__)

PDF_RENDER_SCALE = 2.0  # ~144 DPI; enough for printed text
DETECTION_SIDE = 960  # the text detector works on at most this many pixels
_ONE_AT_A_TIME = threading.Lock()


class OcrUnavailableError(RuntimeError):
    pass


class OcrEngine(Protocol):
    name: str

    def image_to_text(self, image: np.ndarray) -> str: ...


class RapidOcrEngine:
    name = "rapidocr"

    def __init__(self) -> None:
        from rapidocr_onnxruntime import RapidOCR

        threads = max(1, settings.OCR_THREADS)
        self._ocr = RapidOCR(intra_op_num_threads=threads, inter_op_num_threads=threads,
                             max_side_len=settings.OCR_MAX_SIDE, det_limit_side_len=DETECTION_SIDE,
                             det_limit_type="max", use_cls=False)

    def image_to_text(self, image: np.ndarray) -> str:
        result, _ = self._ocr(image)
        if not result:
            return ""
        # Each item: [box(4 points), text, score]. Rebuild reading order by
        # grouping boxes into lines on their vertical centre.
        items = []
        for box, text, _score in result:
            ys = [point[1] for point in box]
            xs = [point[0] for point in box]
            items.append(((min(ys) + max(ys)) / 2, min(xs), max(ys) - min(ys), text))
        items.sort()
        lines: list[list[tuple[float, str]]] = []
        last_y = None
        for centre, left, height, text in items:
            if last_y is None or abs(centre - last_y) > max(height * 0.6, 6):
                lines.append([])
                last_y = centre
            lines[-1].append((left, text))
        return "\n".join(" ".join(text for _, text in sorted(line)) for line in lines)


class TesseractEngine:
    name = "tesseract"

    def __init__(self) -> None:
        import pytesseract  # noqa: F401  (optional dependency)

        if shutil.which("tesseract") is None:
            raise OcrUnavailableError("tesseract binary not found on PATH")
        self._pytesseract = pytesseract

    def image_to_text(self, image: np.ndarray) -> str:
        return self._pytesseract.image_to_string(image)


_ENGINES = {"rapidocr": RapidOcrEngine, "tesseract": TesseractEngine}


@lru_cache(maxsize=1)
def get_engine() -> OcrEngine:
    requested = settings.OCR_ENGINE.strip().casefold()
    if requested == "none":
        raise OcrUnavailableError("OCR is disabled (OCR_ENGINE=none)")
    order = list(_ENGINES) if requested == "auto" else [requested]
    errors = []
    for name in order:
        factory = _ENGINES.get(name)
        if factory is None:
            errors.append(f"{name}: unknown engine")
            continue
        try:
            return factory()
        except Exception as exc:
            errors.append(f"{name}: {type(exc).__name__}: {exc}")
    raise OcrUnavailableError("No OCR engine is available (" + "; ".join(errors) + ")")


def engine_status() -> dict:
    try:
        return {"available": True, "engine": get_engine().name}
    except OcrUnavailableError as exc:
        return {"available": False, "engine": None, "reason": str(exc)}


def decode_image(content: bytes) -> np.ndarray:
    import cv2

    image = cv2.imdecode(np.frombuffer(content, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("The image could not be decoded (corrupt or unsupported encoding)")
    return image


def shrink(image: np.ndarray, max_side: int | None = None) -> np.ndarray:
    """At most ``max_side`` pixels on the longest side (never enlarged)."""
    import cv2

    max_side = max_side or settings.OCR_MAX_SIDE
    height, width = image.shape[:2]
    scale = max_side / max(height, width)
    if scale >= 1:
        return image
    return cv2.resize(image, (max(1, round(width * scale)), max(1, round(height * scale))),
                      interpolation=cv2.INTER_AREA)


def _release_memory() -> None:
    """Hand freed memory back to the system (glibc keeps it otherwise)."""
    gc.collect()
    if sys.platform.startswith("linux"):
        try:
            ctypes.CDLL("libc.so.6").malloc_trim(0)
        except (OSError, AttributeError):
            pass


def read_image(image: np.ndarray) -> str:
    """Text of one image: shrunk first, one document at a time."""
    engine = get_engine()
    with _ONE_AT_A_TIME:
        try:
            return engine.image_to_text(shrink(image))
        finally:
            del image
            _release_memory()


def image_bytes_to_text(content: bytes) -> str:
    return read_image(decode_image(content))


def render_pdf_page(pdf_bytes: bytes, page_index: int) -> np.ndarray:
    import pypdfium2 as pdfium

    document = pdfium.PdfDocument(pdf_bytes)
    try:
        page = document[page_index]
        bitmap = page.render(scale=PDF_RENDER_SCALE)
        image = bitmap.to_numpy()
        # pdfium renders BGRA/BGR; drop alpha if present.
        return np.ascontiguousarray(image[:, :, :3]) if image.ndim == 3 else image
    finally:
        document.close()


def pdf_page_to_text(pdf_bytes: bytes, page_index: int) -> str:
    return read_image(render_pdf_page(pdf_bytes, page_index))

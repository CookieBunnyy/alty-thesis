"""Replaceable OCR layer.

Engines are tried in order (``OCR_ENGINE=auto``): RapidOCR (ONNX, pip-only)
then Tesseract (requires the system binary). Add another engine by
implementing :class:`OcrEngine` and registering it in ``_ENGINES``.
"""

from __future__ import annotations

import logging
import shutil
from functools import lru_cache
from typing import Protocol

import numpy as np

from app.core.config import settings

logger = logging.getLogger(__name__)

PDF_RENDER_SCALE = 2.0  # ~144 DPI; enough for printed text


class OcrUnavailableError(RuntimeError):
    pass


class OcrEngine(Protocol):
    name: str

    def image_to_text(self, image: np.ndarray) -> str: ...


class RapidOcrEngine:
    name = "rapidocr"

    def __init__(self) -> None:
        from rapidocr_onnxruntime import RapidOCR

        self._ocr = RapidOCR()

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


def image_bytes_to_text(content: bytes) -> str:
    return get_engine().image_to_text(decode_image(content))


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
    return get_engine().image_to_text(render_pdf_page(pdf_bytes, page_index))

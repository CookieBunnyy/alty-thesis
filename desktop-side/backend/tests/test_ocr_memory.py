"""Photos are shrunk before their text is read, so a phone photo can't run the
server out of memory (Render's free plan: 512 MB for the whole app)."""

import numpy as np

from app.core.config import settings
from app.services import ocr_service


def test_big_photos_are_shrunk_small_ones_are_kept():
    phone_photo = np.zeros((3024, 4032, 3), np.uint8)
    shrunk = ocr_service.shrink(phone_photo)
    assert max(shrunk.shape[:2]) == settings.OCR_MAX_SIDE
    assert shrunk.shape[0] / shrunk.shape[1] == np.float64(3024 / 4032).round(3) or abs(
        shrunk.shape[0] / shrunk.shape[1] - 3024 / 4032) < 0.01
    small = np.zeros((600, 800, 3), np.uint8)
    assert ocr_service.shrink(small) is small          # never enlarged


def test_reading_releases_the_lock_even_when_it_fails(monkeypatch):
    class Broken:
        name = "broken"

        def image_to_text(self, image):
            raise RuntimeError("engine failed")

    monkeypatch.setattr(ocr_service, "get_engine", lambda: Broken())
    for _ in range(2):  # a stuck lock would hang the second call
        try:
            ocr_service.read_image(np.zeros((10, 10, 3), np.uint8))
        except RuntimeError:
            pass
    assert not ocr_service._ONE_AT_A_TIME.locked()

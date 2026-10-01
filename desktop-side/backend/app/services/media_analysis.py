"""OpenCV image quality analysis for property media.

Scope (deliberately limited): integrity, resolution, orientation, blur,
exposure and contrast. OpenCV alone cannot reliably tell a kitchen from a
bedroom; room/feature recognition needs a trained model and is out of scope.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

# Thresholds (documented so the UI can explain a verdict).
MIN_WIDTH, MIN_HEIGHT = 800, 600          # below: low resolution
RECOMMENDED_PIXELS = 1280 * 720           # below: acceptable, not good
BLUR_POOR, BLUR_OK = 60.0, 150.0          # variance of Laplacian on 1024px-wide gray
DARK, BRIGHT = 50.0, 210.0                # mean gray level
LOW_CONTRAST = 30.0                       # gray standard deviation
THRESHOLDS = {
    "min_resolution": f"{MIN_WIDTH}x{MIN_HEIGHT}",
    "recommended_pixels": RECOMMENDED_PIXELS,
    "blur_variance_poor_below": BLUR_POOR,
    "blur_variance_good_above": BLUR_OK,
    "brightness_range": [DARK, BRIGHT],
    "min_contrast_std": LOW_CONTRAST,
}


@dataclass
class QualityReport:
    width: int | None = None
    height: int | None = None
    orientation: str | None = None
    blur_score: float | None = None
    brightness: float | None = None
    contrast: float | None = None
    status: str = "INVALID"
    issues: list[str] = field(default_factory=list)


def analyze_image(content: bytes) -> QualityReport:
    import cv2

    report = QualityReport()
    image = cv2.imdecode(np.frombuffer(content, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        report.issues.append("File is corrupt or not a decodable image")
        return report

    height, width = image.shape[:2]
    report.width, report.height = int(width), int(height)
    ratio = width / height if height else 0
    report.orientation = "SQUARE" if 0.95 <= ratio <= 1.05 else ("LANDSCAPE" if ratio > 1 else "PORTRAIT")

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if width > 1024:  # normalize scale so blur scores are comparable
        gray = cv2.resize(gray, (1024, int(height * 1024 / width)), interpolation=cv2.INTER_AREA)
    report.blur_score = round(float(cv2.Laplacian(gray, cv2.CV_64F).var()), 2)
    report.brightness = round(float(gray.mean()), 2)
    report.contrast = round(float(gray.std()), 2)

    severe, minor = [], []
    if width < MIN_WIDTH or height < MIN_HEIGHT:
        severe.append(f"Low resolution {width}x{height} (minimum {MIN_WIDTH}x{MIN_HEIGHT})")
    elif width * height < RECOMMENDED_PIXELS:
        minor.append(f"Resolution {width}x{height} is below the recommended 1280x720")
    if report.blur_score < BLUR_POOR:
        severe.append(f"Image appears blurry (sharpness {report.blur_score} < {BLUR_POOR})")
    elif report.blur_score < BLUR_OK:
        minor.append(f"Image is slightly soft (sharpness {report.blur_score})")
    if report.brightness < DARK:
        minor.append(f"Underexposed (mean brightness {report.brightness})")
    elif report.brightness > BRIGHT:
        minor.append(f"Overexposed (mean brightness {report.brightness})")
    if report.contrast < LOW_CONTRAST:
        minor.append(f"Low contrast (std {report.contrast})")
    if report.orientation == "PORTRAIT":
        minor.append("Portrait orientation; listing galleries display landscape best")

    report.issues = severe + minor
    report.status = "POOR" if severe else ("ACCEPTABLE" if minor else "GOOD")
    return report

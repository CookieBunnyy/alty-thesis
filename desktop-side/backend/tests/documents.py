"""Builders for synthetic test documents (DOCX, text PDF, scanned PDF, image)."""

from __future__ import annotations

import io
import zlib

import numpy as np
from docx import Document as WordDocument


def docx(lines: list[str]) -> bytes:
    document = WordDocument()
    for line in lines:
        document.add_paragraph(line)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _pdf(objects: list[bytes]) -> bytes:
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(f"{number} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = out.tell()
    out.write(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets:
        out.write(f"{offset:010d} 00000 n \n".encode())
    out.write(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return out.getvalue()


def text_pdf(lines: list[str]) -> bytes:
    """A PDF with a real text layer (Helvetica)."""
    def escape(value: str) -> str:
        return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    commands = ["BT", "/F1 11 Tf", "14 TL", "50 780 Td"]
    for line in lines:
        commands.append(f"({escape(line)}) Tj T*")
    commands.append("ET")
    stream = zlib.compress("\n".join(commands).encode("latin-1"))
    return _pdf([
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(stream)} /Filter /FlateDecode >>\nstream\n".encode() + stream + b"\nendstream",
    ])


def render_lines(lines: list[str], width: int = 1400, scale: float = 1.1) -> np.ndarray:
    import cv2

    line_height = int(44 * scale)
    image = np.full((line_height * (len(lines) + 2), width, 3), 255, np.uint8)
    for index, line in enumerate(lines, start=1):
        cv2.putText(image, line, (40, index * line_height), cv2.FONT_HERSHEY_SIMPLEX, scale,
                    (0, 0, 0), 2, cv2.LINE_AA)
    return image


def png(lines: list[str]) -> bytes:
    import cv2

    ok, encoded = cv2.imencode(".png", render_lines(lines))
    assert ok
    return encoded.tobytes()


def scanned_pdf(lines: list[str]) -> bytes:
    """An image-only PDF (no text layer) — requires OCR."""
    import cv2

    image = render_lines(lines)
    height, width = image.shape[:2]
    ok, jpeg = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 92])
    assert ok
    jpeg = jpeg.tobytes()
    page_w, page_h = 612, int(612 * height / width)
    content = f"q {page_w} 0 0 {page_h} 0 0 cm /Im1 Do Q".encode()
    return _pdf([
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_w} {page_h}] "
        f"/Resources << /XObject << /Im1 4 0 R >> >> /Contents 5 0 R >>".encode(),
        f"<< /Type /XObject /Subtype /Image /Width {width} /Height {height} /ColorSpace /DeviceRGB "
        f"/BitsPerComponent 8 /Filter /DCTDecode /Length {len(jpeg)} >>\nstream\n".encode()
        + jpeg + b"\nendstream",
        f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream",
    ])


PROPERTY_LINES = [
    "PROPERTY INFORMATION",
    "Listing ID: PROP-TEST-0001",
    "Property Title: Test Property - Azure Heights Residence",
    "Category: House and Lot",
    "Price: PHP 8,500,000.00",
    "Initial Down Payment: PHP 850,000.00",
    "Monthly Rate: PHP 65,000.00",
    "Number of Bedrooms: 3",
    "Number of Bathrooms: 2",
    "Layout Type: Two-Storey",
    "Village Name: Azure Heights Village",
    "Latitude: 14.3512345",
    "Longitude: 120.9876543",
    "Status: AVAILABLE",
    "Has Kitchen: Yes",
    "Has Garage: Yes",
    "Garage Spaces: 2",
    "Amenities: Clubhouse; Swimming Pool; Basketball Court",
    "Nearby Places: Test Academy; Test Medical Center",
    "Details: Three-bedroom two-storey house.",
]

BUYER_LINES = [
    "BUYER INFORMATION RECORD",
    "Client ID: CLI-TEST-0001",
    "Full Name: Michael Santos",
    "Address: Bacoor, Cavite",
    "Contact Number: 0917-555-0101",
    "Email Address: michael.santos.test@example.com",
    "Property ID: PROP-TEST-0001",
    "Property Name: Test Property - Azure Heights Residence",
    "Agent ID: AGT-0006",
    "Agent Name: Daniel Flores",
    "Occupation: Business Owner",
    "Civil Status: Married",
    "Preferred Contact: Mobile",
    "Purpose of Purchase: Residential",
]

RESERVATION_LINES = [
    "RESERVATION AGREEMENT",
    "Reservation ID: RSV-TEST-0001",
    "Client ID: CLI-TEST-0001",
    "Buyer Name: Michael Santos",
    "Email: michael.santos.test@example.com",
    "Listing ID: PROP-TEST-0001",
    "Agent ID: AGT-0006",
    "Agent Name: Daniel Flores",
    "Reservation Date: September 30, 2026",
    "Reservation Amount: PHP 50,000.00",
]

SALE_LINES = [
    "SALE AGREEMENT",
    "Transaction ID: SALE-TEST-0001",
    "Reservation ID: RSV-TEST-0001",
    "Client ID: CLI-TEST-0001",
    "Buyer Name: Michael Santos",
    "Listing ID: PROP-TEST-0001",
    "Agent ID: AGT-0006",
    "Sale Date: 10/15/2026",
    "Sale Amount: PHP 8,500,000.00",
]

AGENT_LINES = [
    "AGENT INFORMATION",
    "Agent ID: AGT-0003",
    "Full Name: Angela Cruz",
    "Agent Phone Number: 0917-000-0003",
    "Agent Location: Quezon City",
    "Star Rating: 4.9",
    "Completed Sales: 12",
    "Performance Score: 91.5",
    "Agent Status: ACTIVE",
]

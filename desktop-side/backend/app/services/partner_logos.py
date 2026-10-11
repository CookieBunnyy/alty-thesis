"""Partner logos for the public home page.

Unlike profile photos, a logo keeps its shape and transparency: the upload
(a real JPEG/PNG/WEBP image, at most 5 MB; no SVG, which can carry scripts)
is scaled to fit 480×200 and saved as a PNG. Stored with the same file
storage as documents and photos.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from io import BytesIO

from fastapi import HTTPException, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError

from app.models.partner import Partner
from app.services.document_storage import StorageError, delete_file, read_file, store_file

MAX_BYTES = 5 * 1024 * 1024
BOX = (480, 200)
ALLOWED = {"JPEG", "PNG", "WEBP"}


def logo_version(partner: Partner) -> int | None:
    if not partner.logo_path or not partner.logo_updated_at:
        return None
    return int(partner.logo_updated_at.replace(tzinfo=timezone.utc).timestamp())


def _logo_png(content: bytes) -> bytes:
    try:
        image = Image.open(BytesIO(content))
        image_format = image.format
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(status_code=422, detail="The file isn't a readable image") from exc
    if image_format not in ALLOWED:
        raise HTTPException(status_code=422, detail="Use a JPG, PNG or WEBP logo")
    image = ImageOps.exif_transpose(image).convert("RGBA")
    if max(image.size) < 48:
        raise HTTPException(status_code=422, detail="The logo is too small (at least 48 pixels wide)")
    image.thumbnail(BOX, Image.Resampling.LANCZOS)
    out = BytesIO()
    image.save(out, format="PNG", optimize=True)
    return out.getvalue()


async def save_logo(partner: Partner, upload: UploadFile) -> None:
    """Replace the partner's logo with the uploaded one (caller commits)."""
    content = await upload.read(MAX_BYTES + 1)
    if not content:
        raise HTTPException(status_code=422, detail="The file is empty")
    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="Logos must be 5 MB or smaller")
    logo = _logo_png(content)
    path = f"partner-logos/{partner.id}-{secrets.token_hex(6)}.png"
    try:
        bucket = store_file("media", path, logo, "image/png")
    except StorageError as exc:
        raise HTTPException(status_code=502, detail="The logo could not be stored") from exc
    remove_logo(partner)
    partner.logo_bucket, partner.logo_path = bucket, path
    partner.logo_updated_at = datetime.now(timezone.utc).replace(tzinfo=None)


def remove_logo(partner: Partner) -> None:
    if partner.logo_bucket and partner.logo_path:
        try:
            delete_file(partner.logo_bucket, partner.logo_path)
        except StorageError:
            pass  # an orphaned file is harmless
    partner.logo_bucket = partner.logo_path = None
    partner.logo_updated_at = None


def logo_bytes(partner: Partner) -> bytes:
    if not partner.logo_bucket or not partner.logo_path:
        raise HTTPException(status_code=404, detail="No logo")
    try:
        return read_file(partner.logo_bucket, partner.logo_path)
    except StorageError as exc:
        raise HTTPException(status_code=404, detail="Logo unavailable") from exc

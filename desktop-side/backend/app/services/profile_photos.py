"""Profile photos for agents and staff accounts.

An upload is checked (a real JPEG/PNG/WEBP image, at most 8 MB), turned
upright, cropped to a centred square and saved as a 512×512 JPEG, so every
photo is small and the same shape. Stored with the same file storage as
documents (Supabase storage, or local files in development).
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from io import BytesIO
from typing import Protocol

from fastapi import HTTPException, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError

from app.services.document_storage import StorageError, delete_file, read_file, store_file

MAX_BYTES = 8 * 1024 * 1024
SIZE = 512
ALLOWED = {"JPEG", "PNG", "WEBP"}


class HasPhoto(Protocol):
    photo_bucket: str | None
    photo_path: str | None
    photo_updated_at: datetime | None


def photo_version(owner: HasPhoto) -> int | None:
    """Changes whenever the photo changes (used to refresh cached images)."""
    if not owner.photo_path or not owner.photo_updated_at:
        return None
    return int(owner.photo_updated_at.replace(tzinfo=timezone.utc).timestamp())


def _square_jpeg(content: bytes) -> bytes:
    try:
        image = Image.open(BytesIO(content))
        image_format = image.format
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(status_code=422, detail="The file isn't a readable image") from exc
    if image_format not in ALLOWED:
        raise HTTPException(status_code=422, detail="Use a JPG, PNG or WEBP photo")
    image = ImageOps.exif_transpose(image).convert("RGB")
    if min(image.size) < 96:
        raise HTTPException(status_code=422, detail="The photo is too small (at least 96×96 pixels)")
    image = ImageOps.fit(image, (SIZE, SIZE), Image.Resampling.LANCZOS, centering=(0.5, 0.4))
    out = BytesIO()
    image.save(out, format="JPEG", quality=86, optimize=True)
    return out.getvalue()


async def save_photo(owner: HasPhoto, kind: str, owner_id: str | int, upload: UploadFile) -> None:
    """Replace ``owner``'s photo with the uploaded one (caller commits)."""
    content = await upload.read(MAX_BYTES + 1)
    if not content:
        raise HTTPException(status_code=422, detail="The file is empty")
    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="Photos must be 8 MB or smaller")
    photo = _square_jpeg(content)
    path = f"profile-photos/{kind}/{owner_id}-{secrets.token_hex(6)}.jpg"
    try:
        bucket = store_file("media", path, photo, "image/jpeg")
    except StorageError as exc:
        raise HTTPException(status_code=502, detail="The photo could not be stored") from exc
    remove_photo(owner)
    owner.photo_bucket, owner.photo_path = bucket, path
    owner.photo_updated_at = datetime.now(timezone.utc).replace(tzinfo=None)


def remove_photo(owner: HasPhoto) -> None:
    """Forget the photo (the stored file is deleted when possible)."""
    if owner.photo_bucket and owner.photo_path:
        try:
            delete_file(owner.photo_bucket, owner.photo_path)
        except StorageError:
            pass  # an orphaned file is harmless; the record no longer points at it
    owner.photo_bucket = owner.photo_path = None
    owner.photo_updated_at = None


def photo_bytes(owner: HasPhoto) -> bytes:
    if not owner.photo_bucket or not owner.photo_path:
        raise HTTPException(status_code=404, detail="No photo")
    try:
        return read_file(owner.photo_bucket, owner.photo_path)
    except StorageError as exc:
        raise HTTPException(status_code=404, detail="Photo unavailable") from exc

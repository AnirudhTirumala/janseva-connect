"""Safe on-disk handling for citizen-provided application documents."""

from pathlib import Path
import uuid

from app.core.config import settings


ALLOWED_CONTENT_TYPES = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
}
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024

# Kept read-only for records written by pre-storage-path versions of the
# application. New uploads are always written under STORAGE_PATH.
LEGACY_UPLOAD_DIR = (Path(__file__).resolve().parents[1] / "uploaded_documents").resolve()


def upload_dir() -> Path:
    directory = (settings.storage_path / "uploads").resolve()
    directory.mkdir(parents=True, exist_ok=True)
    return directory


async def read_upload_within_limit(file, limit: int = MAX_FILE_SIZE_BYTES) -> bytes:
    """Read an upload in chunks, aborting as soon as it exceeds the cap.

    ``await file.read()`` buffers the entire body first and only then
    compares its length, so a single request advertising a multi-gigabyte
    document could exhaust the instance's memory before the 5 MB check ever
    ran. Reading incrementally means an oversized upload is rejected after
    one chunk past the limit, no matter what the client claims.
    """
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise ValueError("File is too large - maximum size is 5 MB.")
        chunks.append(chunk)
    return b"".join(chunks)


def canonical_content_type(content_type: str | None, content: bytes) -> str:
    """Validate declared type *and* file signature, returning a safe type."""
    declared = (content_type or "").lower().strip()
    if declared not in ALLOWED_CONTENT_TYPES:
        raise ValueError("Only PDF, JPG, or PNG files are accepted.")

    if declared == "application/pdf":
        valid, canonical = content.startswith(b"%PDF-"), "application/pdf"
    elif declared in {"image/jpeg", "image/jpg"}:
        valid, canonical = content.startswith(b"\xff\xd8\xff"), "image/jpeg"
    else:
        valid, canonical = content.startswith(b"\x89PNG\r\n\x1a\n"), "image/png"
    if not valid:
        raise ValueError("The uploaded file does not match its declared PDF, JPG, or PNG type.")
    return canonical


def save_uploaded_file(application_id: int, content_type: str, content: bytes) -> str:
    """Store a document with a random filename and an allow-listed suffix."""
    root = upload_dir()
    app_dir = (root / str(application_id)).resolve()
    if app_dir.parent != root:
        raise ValueError("Invalid application storage path")
    app_dir.mkdir(parents=True, exist_ok=True)

    safe_name = f"{uuid.uuid4().hex}{ALLOWED_CONTENT_TYPES[content_type]}"
    file_path = app_dir / safe_name
    file_path.write_bytes(content)
    return str(file_path)


def safe_document_path(file_path: str | None) -> Path | None:
    """Return a record's path only if it is inside an approved storage root."""
    if not file_path:
        return None
    candidate = Path(file_path).resolve()
    roots = (upload_dir(), LEGACY_UPLOAD_DIR)
    if not any(candidate.is_relative_to(root) for root in roots):
        return None
    return candidate if candidate.is_file() else None


def delete_uploaded_file(file_path: str | None) -> None:
    """Best-effort cleanup for a corrected/replaced upload."""
    candidate = safe_document_path(file_path)
    if candidate:
        candidate.unlink(missing_ok=True)

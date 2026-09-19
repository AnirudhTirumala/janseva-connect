"""Safe handling of citizen-provided application documents."""

from pathlib import Path
import uuid

from app.core.config import settings
from app.utils.supabase_storage import (
    download_file,
    upload_file,
    delete_file,
)

ALLOWED_CONTENT_TYPES = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
}

MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024

LEGACY_UPLOAD_DIR = (
    Path(__file__).resolve().parents[1] / "uploaded_documents"
).resolve()


def upload_dir() -> Path:
    directory = (settings.storage_path / "uploads").resolve()
    directory.mkdir(parents=True, exist_ok=True)
    return directory


async def read_upload_within_limit(
    file,
    limit: int = MAX_FILE_SIZE_BYTES,
) -> bytes:
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


def canonical_content_type(
    content_type: str | None,
    content: bytes,
) -> str:
    declared = (content_type or "").lower().strip()

    if declared not in ALLOWED_CONTENT_TYPES:
        raise ValueError("Only PDF, JPG, or PNG files are accepted.")

    if declared == "application/pdf":
        valid, canonical = content.startswith(b"%PDF-"), "application/pdf"

    elif declared in {"image/jpeg", "image/jpg"}:
        valid, canonical = content.startswith(b"\xff\xd8\xff"), "image/jpeg"

    else:
        valid, canonical = (
            content.startswith(b"\x89PNG\r\n\x1a\n"),
            "image/png",
        )

    if not valid:
        raise ValueError(
            "The uploaded file does not match its declared PDF, JPG, or PNG type."
        )

    return canonical


def save_uploaded_file(
    application_id: int,
    content_type: str,
    content: bytes,
) -> str:
    extension = ALLOWED_CONTENT_TYPES[content_type]
    object_path = f"{application_id}/{uuid.uuid4().hex}{extension}"

    if settings.supabase_storage_is_configured:
        return upload_file(
            settings.SUPABASE_DOCUMENTS_BUCKET,
            object_path,
            content,
            content_type,
        )

    # Local-development fallback.
    root = upload_dir()
    app_dir = (root / str(application_id)).resolve()

    if app_dir.parent != root:
        raise ValueError("Invalid application storage path")

    app_dir.mkdir(parents=True, exist_ok=True)

    file_path = app_dir / f"{uuid.uuid4().hex}{extension}"
    file_path.write_bytes(content)

    return str(file_path)


def read_uploaded_file(
    file_path: str | None,
) -> bytes | None:
    if not file_path:
        return None

    if settings.supabase_storage_is_configured:
        try:
            return download_file(
                settings.SUPABASE_DOCUMENTS_BUCKET,
                file_path,
            )
        except Exception:
            return None

    file = safe_document_path(file_path)

    if not file:
        return None

    try:
        return file.read_bytes()
    except OSError:
        return None


def safe_document_path(
    file_path: str | None,
) -> Path | None:
    if not file_path:
        return None

    candidate = Path(file_path).resolve()
    roots = (upload_dir(), LEGACY_UPLOAD_DIR)

    if not any(candidate.is_relative_to(root) for root in roots):
        return None

    return candidate if candidate.is_file() else None


def delete_uploaded_file(
    file_path: str | None,
) -> None:
    if not file_path:
        return

    if settings.supabase_storage_is_configured:
        delete_file(
            settings.SUPABASE_DOCUMENTS_BUCKET,
            file_path,
        )
        return

    candidate = safe_document_path(file_path)

    if candidate:
        candidate.unlink(missing_ok=True)
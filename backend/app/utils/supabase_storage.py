"""Server-side helpers for private Supabase Storage buckets."""

from functools import lru_cache

from supabase import create_client, Client

from app.core.config import settings


@lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    if not settings.supabase_storage_is_configured:
        raise RuntimeError(
            "Supabase Storage is not configured. "
            "Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY."
        )

    return create_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_SERVICE_ROLE_KEY,
    )


def upload_file(
    bucket: str,
    object_path: str,
    content: bytes,
    content_type: str,
) -> str:
    """Upload/replace a private Supabase Storage object."""
    client = get_supabase_client()

    client.storage.from_(bucket).upload(
        object_path,
        content,
        {
            "content-type": content_type,
            "upsert": "true",
        },
    )

    return object_path


def download_file(bucket: str, object_path: str) -> bytes:
    """Download a private object using the server-side service role."""
    client = get_supabase_client()
    return client.storage.from_(bucket).download(object_path)


def delete_file(bucket: str, object_path: str) -> None:
    """Delete a private Storage object if it exists."""
    client = get_supabase_client()

    try:
        client.storage.from_(bucket).remove([object_path])
    except Exception:
        # Deletion should not prevent removal of the corresponding database
        # record when the object is already missing.
        pass
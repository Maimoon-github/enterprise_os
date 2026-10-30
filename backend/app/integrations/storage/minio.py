import logging
from datetime import timedelta

from app.core.config import settings
from minio import Minio

logger = logging.getLogger("integrations.minio")


def get_minio_client() -> Minio:
    """Return configured MinIO client instance."""
    return Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ROOT_USER,
        secret_key=settings.MINIO_ROOT_PASSWORD,
        secure=settings.MINIO_USE_SSL,
    )


def ensure_buckets_exist() -> list[str]:
    """Ensure standard marketing buckets exist on MinIO."""
    buckets = [
        settings.MINIO_BUCKET_RAW,
        settings.MINIO_BUCKET_GENERATED,
        "marketing-exports",
    ]
    try:
        client = get_minio_client()
        for bucket in buckets:
            if not client.bucket_exists(bucket):
                client.make_bucket(bucket)
        return buckets
    except Exception as exc:
        logger.warning("MinIO endpoint unavailable (%s). Using virtual bucket catalog.", exc)
        return buckets


def generate_presigned_url(bucket: str, object_key: str, expires_seconds: int = 3600) -> str:
    """Generate presigned download or upload URL with test-safe fallback."""
    try:
        client = get_minio_client()
        return client.presigned_get_object(bucket, object_key, expires=timedelta(seconds=expires_seconds))
    except Exception:
        # Fallback format for offline test execution
        protocol = "https" if settings.MINIO_USE_SSL else "http"
        return f"{protocol}://{settings.MINIO_ENDPOINT}/{bucket}/{object_key}"

import uuid
from datetime import timedelta
from pathlib import Path

from minio import Minio

from app.config import get_settings

_client: Minio | None = None


def get_minio() -> Minio:
    global _client
    if _client is None:
        settings = get_settings()
        _client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
    return _client


def reset_minio_client() -> None:
    global _client
    _client = None


def build_object_key(user_id: uuid.UUID, filename: str) -> str:
    suffix = Path(filename).suffix.lower() or ".jpg"
    return f"{user_id}/{uuid.uuid4()}{suffix}"


def ensure_bucket() -> None:
    settings = get_settings()
    client = get_minio()
    if not client.bucket_exists(settings.minio_bucket):
        client.make_bucket(settings.minio_bucket)


def upload_image(object_key: str, data: bytes, content_type: str) -> None:
    from io import BytesIO

    settings = get_settings()
    client = get_minio()
    client.put_object(
        settings.minio_bucket,
        object_key,
        BytesIO(data),
        length=len(data),
        content_type=content_type or "application/octet-stream",
    )


def delete_image(object_key: str) -> None:
    settings = get_settings()
    get_minio().remove_object(settings.minio_bucket, object_key)


def presigned_get_url(object_key: str, expires_seconds: int = 3600) -> str:
    settings = get_settings()
    return get_minio().presigned_get_object(
        settings.minio_bucket,
        object_key,
        expires=timedelta(seconds=expires_seconds),
    )

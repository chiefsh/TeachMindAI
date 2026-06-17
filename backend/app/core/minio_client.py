from minio import Minio
from minio.error import S3Error
from app.core.config import settings
import io

client = Minio(
    settings.MINIO_ENDPOINT,
    access_key=settings.MINIO_ACCESS_KEY,
    secret_key=settings.MINIO_SECRET_KEY,
    secure=settings.MINIO_SECURE,
)

BUCKETS = [
    settings.MINIO_BUCKET_TEXTBOOKS,
    settings.MINIO_BUCKET_QUESTIONS,
    settings.MINIO_BUCKET_COURSEWARES,
]


def init_buckets():
    for bucket in BUCKETS:
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)


def upload_file(bucket: str, object_name: str, data: bytes, content_type: str) -> str:
    client.put_object(
        bucket,
        object_name,
        io.BytesIO(data),
        length=len(data),
        content_type=content_type,
    )
    return object_name


def get_presigned_url(bucket: str, object_name: str, expires_hours: int = 2) -> str:
    from datetime import timedelta
    return client.presigned_get_object(bucket, object_name, expires=timedelta(hours=expires_hours))


def delete_file(bucket: str, object_name: str):
    try:
        client.remove_object(bucket, object_name)
    except S3Error:
        pass


def get_file_bytes(bucket: str, object_name: str) -> bytes:
    response = client.get_object(bucket, object_name)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()

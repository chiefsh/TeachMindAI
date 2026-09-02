from minio import Minio
from minio.error import S3Error
from app.core.config import settings
import io


def _split_endpoint(value: str, default_secure: bool) -> tuple[str, bool]:
    raw = (value or "").strip()
    if raw.startswith("https://"):
        return raw[8:].rstrip("/"), True
    if raw.startswith("http://"):
        return raw[7:].rstrip("/"), False
    return raw.rstrip("/"), default_secure


_internal_host, _internal_secure = _split_endpoint(settings.MINIO_ENDPOINT, settings.MINIO_SECURE)

client = Minio(
    _internal_host,
    access_key=settings.MINIO_ACCESS_KEY,
    secret_key=settings.MINIO_SECRET_KEY,
    secure=_internal_secure,
)


def _make_public_client() -> Minio:
    """预签名必须用浏览器能访问的 Host 签发，V4 签名绑定主机名，不能事后替换。"""
    public_raw = (settings.MINIO_PUBLIC_ENDPOINT or "").strip()
    if not public_raw:
        return client
    host, secure = _split_endpoint(public_raw, settings.MINIO_PUBLIC_SECURE)
    if host == _internal_host and secure == _internal_secure:
        return client
    # region 固定后签发不访问外网 Host（容器内 localhost:9000 并不是宿主机 MinIO）
    return Minio(
        host,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=secure,
        region="us-east-1",
    )


_public_client = _make_public_client()

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


def get_presigned_url(
    bucket: str,
    object_name: str,
    expires_hours: int = 2,
    response_headers: dict | None = None,
) -> str:
    from datetime import timedelta
    kwargs: dict = {"expires": timedelta(hours=expires_hours)}
    if response_headers:
        kwargs["response_headers"] = response_headers
    return _public_client.presigned_get_object(bucket, object_name, **kwargs)


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

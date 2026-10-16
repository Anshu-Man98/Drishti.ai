import hashlib
from pathlib import Path
from typing import Tuple, Any
from backend.app.config import settings
from backend.app.exceptions import CloudServiceError

try:
    from google.cloud import storage
    _gcs_available = True
except Exception:
    _gcs_available = False


class StorageService:
    """
    Cloud-native Google Cloud Storage Service.
    All claims documents, rendered page images, and signed sanction PDFs
    live exclusively in GCS bucket.
    There is no local or in-memory blob fallback.
    """
    def __init__(self):
        self.bucket_name = settings.GCS_BUCKET_NAME
        self._client = None
        self._init_client()

    def _init_client(self):
        if _gcs_available and settings.GCP_PROJECT:
            try:
                self._client = storage.Client(project=settings.GCP_PROJECT)
            except Exception as e:
                self._client = None
                if settings.REQUIRE_CLOUD_ON_STARTUP:
                    raise CloudServiceError(
                        service="gcs",
                        message=f"Failed to initialize GCS client for project '{settings.GCP_PROJECT}': {e}",
                        retryable=True
                    )

    @property
    def client(self) -> Any:
        if self._client is None:
            self._init_client()
        if self._client is None:
            raise CloudServiceError(
                service="gcs",
                message="Google Cloud Storage client is unavailable. Live GCS connection required.",
                retryable=True
            )
        return self._client

    def upload_file(self, file_bytes: bytes, filename: str, claim_id: str) -> Tuple[str, str]:
        """
        Uploads file bytes directly to Google Cloud Storage.
        Returns: (gcs_uri, sha256_hash)
        """
        sha256 = hashlib.sha256(file_bytes).hexdigest()
        ext = Path(filename).suffix
        if filename.startswith("pages/"):
            destination_name = f"uploads/{claim_id}/{filename}"
        else:
            destination_name = f"uploads/{claim_id}/{sha256}{ext}"

        gcs_uri = f"gs://{self.bucket_name}/{destination_name}"

        try:
            bucket = self.client.bucket(self.bucket_name)
            blob = bucket.blob(destination_name)
            blob.upload_from_string(file_bytes)
        except Exception as e:
            raise CloudServiceError(
                service="gcs",
                message=f"Failed to upload document to GCS ({gcs_uri}): {e}",
                retryable=True
            )

        return gcs_uri, sha256

    def read_file(self, uri: str) -> bytes:
        """
        Reads bytes directly from Google Cloud Storage (or test fixture file:// URI).
        """
        if uri.startswith("file://"):
            local_path = Path(uri.replace("file://", "")).resolve()
            if not local_path.exists() or not local_path.is_file():
                raise FileNotFoundError(f"Local test file not found: {local_path}")
            return local_path.read_bytes()

        if not uri.startswith("gs://"):
            raise ValueError(f"Cloud-only storage violation: URI must start with gs://, received: {uri}")

        parts = uri.replace("gs://", "").split("/", 1)
        bucket_name = parts[0]
        blob_name = parts[1] if len(parts) > 1 else ""

        ALLOWED_PREFIXES = ("uploads/", "claims/")
        if bucket_name != self.bucket_name or not any(blob_name.startswith(p) for p in ALLOWED_PREFIXES):
            raise PermissionError(f"Security error: Invalid GCS storage path or bucket: {uri}")

        try:
            bucket = self.client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            return blob.download_as_bytes()
        except Exception as e:
            raise CloudServiceError(
                service="gcs",
                message=f"Failed to download document from GCS ({uri}): {e}",
                retryable=True
            )


storage_service = StorageService()

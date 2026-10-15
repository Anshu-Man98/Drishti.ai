import os
import hashlib
from pathlib import Path
from typing import Tuple
from backend.app.config import settings

try:
    from google.cloud import storage
    _gcs_available = True
except Exception:
    _gcs_available = False


class StorageService:
    def __init__(self):
        self.bucket_name = settings.GCS_BUCKET_NAME
        self.local_dir = Path(settings.LOCAL_DATA_DIR) / "uploads"
        self.local_dir.mkdir(parents=True, exist_ok=True)
        self._client = None
        if _gcs_available and not settings.LOCAL_FALLBACK:
            try:
                self._client = storage.Client(project=settings.GCP_PROJECT)
            except Exception:
                self._client = None

    def upload_file(self, file_bytes: bytes, filename: str, claim_id: str) -> Tuple[str, str]:
        """
        Uploads file bytes either to GCS or to local fallback directory.
        Returns: (uri, sha256_hash)
        """
        sha256 = hashlib.sha256(file_bytes).hexdigest()
        ext = Path(filename).suffix
        destination_name = f"{claim_id}/{sha256}{ext}"

        if self._client:
            try:
                bucket = self._client.bucket(self.bucket_name)
                blob = bucket.blob(destination_name)
                blob.upload_from_string(file_bytes)
                return f"gs://{self.bucket_name}/{destination_name}", sha256
            except Exception as e:
                print(f"[StorageService] GCS upload failed, falling back to local: {e}")

        # Local storage fallback
        claim_local_dir = self.local_dir / claim_id
        claim_local_dir.mkdir(parents=True, exist_ok=True)
        dest_path = claim_local_dir / f"{sha256}{ext}"
        with open(dest_path, "wb") as f:
            f.write(file_bytes)

        return f"file://{dest_path.absolute()}", sha256

    def read_file(self, uri: str) -> bytes:
        if uri.startswith("file://"):
            raw_path = uri.replace("file://", "")
            local_path = Path(raw_path).resolve()
            allowed_roots = [
                self.local_dir.resolve(),
                Path(settings.LOCAL_DATA_DIR).resolve()
            ]
            if not any(str(local_path).startswith(str(root)) for root in allowed_roots):
                raise PermissionError(f"Security error: Access denied to path outside allowed storage roots: {local_path}")
            if not local_path.exists():
                raise FileNotFoundError(f"File not found: {local_path}")
            with open(local_path, "rb") as f:
                return f.read()
        elif uri.startswith("gs://"):
            parts = uri.replace("gs://", "").split("/", 1)
            bucket_name = parts[0]
            blob_name = parts[1] if len(parts) > 1 else ""
            if bucket_name != self.bucket_name or not blob_name.startswith("uploads/"):
                raise PermissionError(f"Security error: Invalid GCS storage path or bucket: {uri}")
            if self._client:
                bucket = self._client.bucket(bucket_name)
                blob = bucket.blob(blob_name)
                return blob.download_as_bytes()
            raise FileNotFoundError(f"GCS client unavailable for storage read: {uri}")
        else:
            raise FileNotFoundError(f"Unsupported URI scheme for storage read: {uri}")


storage_service = StorageService()

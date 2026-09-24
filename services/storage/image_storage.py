"""Cloud Storage abstraction for citizen report images.

Provides an abstract base provider, a local development provider,
and a Google Cloud Storage provider that uses Application Default Credentials (ADC)
and stores images as private objects.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
from typing import Optional, Tuple
import uuid

from apps.api.config import get_settings


class ImageStorageProvider(ABC):
    """Abstract interface for storing and retrieving uploaded report images."""

    @abstractmethod
    def store_image(
        self,
        image_bytes: bytes,
        mime_type: str = "image/jpeg",
        filename: Optional[str] = None,
    ) -> Tuple[str, str]:
        """Store an image and return (storage_uri, public_or_signed_url)."""
        pass

    @abstractmethod
    def retrieve_image(self, storage_uri: str) -> bytes:
        """Retrieve the raw image bytes from storage URI."""
        pass


class LocalImageStorageProvider(ImageStorageProvider):
    """Local filesystem storage for offline development, fixtures, and unit testing."""

    def __init__(self, base_dir: Optional[Path] = None):
        if base_dir is None:
            self.base_dir = Path("data/uploads").resolve()
        else:
            self.base_dir = Path(base_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def store_image(
        self,
        image_bytes: bytes,
        mime_type: str = "image/jpeg",
        filename: Optional[str] = None,
    ) -> Tuple[str, str]:
        ext = ".jpg" if "jpeg" in mime_type.lower() else ".png"
        if filename and "." in filename:
            ext = Path(filename).suffix or ext

        file_id = f"{uuid.uuid4().hex[:12]}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}{ext}"
        target_path = self.base_dir / file_id
        target_path.write_bytes(image_bytes)

        storage_uri = f"file://{target_path.as_posix()}"
        # For local development, URL can point to the local file path or mock URL
        return storage_uri, storage_uri

    def retrieve_image(self, storage_uri: str) -> bytes:
        if storage_uri.startswith("file://"):
            path = Path(storage_uri.replace("file://", ""))
        else:
            path = Path(storage_uri)
        if not path.exists():
            raise FileNotFoundError(f"Image not found at path: {path}")
        return path.read_bytes()


class CloudStorageProvider(ImageStorageProvider):
    """Google Cloud Storage provider storing private objects using ADC."""

    def __init__(self, bucket_name: str, project_id: Optional[str] = None):
        self.bucket_name = bucket_name
        self.project_id = project_id
        try:
            from google.cloud import storage

            self.client = storage.Client(project=project_id)
            self.bucket = self.client.bucket(bucket_name)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to initialize Google Cloud Storage client for bucket '{bucket_name}': {exc}"
            ) from exc

    def store_image(
        self,
        image_bytes: bytes,
        mime_type: str = "image/jpeg",
        filename: Optional[str] = None,
    ) -> Tuple[str, str]:
        ext = ".jpg" if "jpeg" in mime_type.lower() else ".png"
        if filename and "." in filename:
            ext = Path(filename).suffix or ext

        # Partition by date for organized Cloud Storage bucket structure
        date_prefix = datetime.now(timezone.utc).strftime("%Y/%m/%d")
        object_name = f"citizen_reports/{date_prefix}/{uuid.uuid4().hex}{ext}"

        blob = self.bucket.blob(object_name)
        # Store as private object
        blob.upload_from_string(
            image_bytes,
            content_type=mime_type,
        )

        storage_uri = f"gs://{self.bucket_name}/{object_name}"
        # Internal reference or gs URI (no public world-readable access)
        return storage_uri, storage_uri

    def retrieve_image(self, storage_uri: str) -> bytes:
        if not storage_uri.startswith(f"gs://{self.bucket_name}/"):
            raise ValueError(f"Invalid Cloud Storage URI for bucket {self.bucket_name}: {storage_uri}")

        object_name = storage_uri[len(f"gs://{self.bucket_name}/"):]
        blob = self.bucket.blob(object_name)
        return blob.download_as_bytes()


_storage_provider_instance: Optional[ImageStorageProvider] = None


def get_image_storage_provider() -> ImageStorageProvider:
    """Factory to get the configured image storage provider."""
    global _storage_provider_instance
    if _storage_provider_instance is not None:
        return _storage_provider_instance

    settings = get_settings()
    bucket_name = getattr(settings, "STORAGE_BUCKET", None) or os.getenv("STORAGE_BUCKET")

    if settings.ENV == "production":
        if not bucket_name:
            raise RuntimeError(
                "STORAGE_BUCKET is required in production environment for secure image storage."
            )
        _storage_provider_instance = CloudStorageProvider(
            bucket_name=bucket_name,
            project_id=settings.GOOGLE_CLOUD_PROJECT,
        )
    else:
        # Development or test environment
        if bucket_name and not os.getenv("PYTEST_CURRENT_TEST"):
            try:
                _storage_provider_instance = CloudStorageProvider(
                    bucket_name=bucket_name,
                    project_id=settings.GOOGLE_CLOUD_PROJECT,
                )
            except Exception:
                _storage_provider_instance = LocalImageStorageProvider()
        else:
            _storage_provider_instance = LocalImageStorageProvider()

    return _storage_provider_instance


def reset_image_storage_provider() -> None:
    """Reset the singleton instance (useful for testing)."""
    global _storage_provider_instance
    _storage_provider_instance = None

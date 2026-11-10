import os
import uuid
from typing import Optional

from app.core.config import settings


class LocalStorageService:
    """Stores uploaded source files on the local filesystem under STORAGE_DIR.

    Files are written with random names (storage keys) to avoid collisions
    and path traversal issues. The directory is created on demand.
    """

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = base_dir or settings.STORAGE_DIR

    def _ensure_dir(self) -> None:
        os.makedirs(self.base_dir, exist_ok=True)

    def save_file(self, raw_bytes: bytes) -> str:
        """Persist bytes and return the storage key (filename)."""
        self._ensure_dir()
        storage_key = f"{uuid.uuid4().hex}.bin"
        path = os.path.join(self.base_dir, storage_key)
        with open(path, "wb") as f:
            f.write(raw_bytes)
        return storage_key

    def read_file(self, storage_key: str) -> Optional[bytes]:
        """Read back file contents, or None if missing."""
        if not storage_key:
            return None
        path = os.path.join(self.base_dir, os.path.basename(storage_key))
        if not os.path.isfile(path):
            return None
        with open(path, "rb") as f:
            return f.read()

    def delete_file(self, storage_key: str) -> bool:
        """Delete a stored file. Returns True if a file was removed."""
        if not storage_key:
            return False
        path = os.path.join(self.base_dir, os.path.basename(storage_key))
        if os.path.isfile(path):
            try:
                os.remove(path)
                return True
            except OSError:
                return False
        return False


storage_service = LocalStorageService()

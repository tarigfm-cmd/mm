import os
from pathlib import Path

from fastapi import UploadFile

from app.config import get_settings

settings = get_settings()


class FileValidationError(ValueError):
    pass


def validate_upload_file(file: UploadFile) -> None:
    """Validate file type and enforce size limits at the handler level."""
    if not file.filename:
        raise FileValidationError("File has no name.")

    ext = Path(file.filename).suffix.lstrip(".").lower()
    if ext not in settings.allowed_extensions:
        raise FileValidationError(
            f"File type '.{ext}' is not allowed. "
            f"Allowed types: {', '.join(settings.allowed_extensions)}"
        )


def build_upload_path(filename: str) -> Path:
    """Return absolute path for storing uploaded file, creating directories as needed."""
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(filename).name  # strip any path traversal
    return upload_dir / safe_name


def human_readable_size(size_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes //= 1024
    return f"{size_bytes:.1f} TB"

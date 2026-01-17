"""File path utilities for Exam Manager."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from flask import current_app


def get_upload_folder(admin: bool = False) -> Path:
    """Get upload folder path."""
    if admin:
        return Path(current_app.static_folder) / "uploads_admin"
    return Path(current_app.config["UPLOAD_FOLDER"])


def get_pdf_crop_folder(upload_folder: Optional[Path] = None) -> Path:
    """Get PDF crop folder path."""
    if upload_folder is None:
        upload_folder = get_upload_folder()
    return upload_folder / "crops"


def get_question_image_path(
    question_id: int, filename: str, admin: bool = False
) -> Path:
    """Get storage path for a question image."""
    upload_folder = get_upload_folder(admin)
    return upload_folder / "questions" / str(question_id) / filename


def get_exam_image_path(exam_id: int, filename: str, admin: bool = False) -> Path:
    """Get storage path for an exam image."""
    upload_folder = get_upload_folder(admin)
    return upload_folder / "exams" / str(exam_id) / filename


def get_pdf_page_path(exam_id: int, page_num: int, admin: bool = False) -> Path:
    """Get storage path for a PDF page crop."""
    upload_folder = get_upload_folder(admin)
    return (
        get_pdf_crop_folder(upload_folder) / str(exam_id) / f"page_{page_num:04d}.png"
    )


def get_pdf_merged_path(question_id: int, qnum: int, admin: bool = False) -> Path:
    """Get storage path for a merged PDF page image."""
    upload_folder = get_upload_folder(admin)
    return (
        get_pdf_crop_folder(upload_folder)
        / str(question_id)
        / f"Q{qnum:02d}_merged.png"
    )


def sanitize_filename(filename: str) -> str:
    """Sanitize a filename to remove problematic characters."""
    filename = filename.replace("\\", "").replace("/", "")
    keep_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._- "
    return "".join(c for c in filename if c in keep_chars)


def ensure_directory_exists(path: Path) -> None:
    """Ensure a directory exists, creating it if necessary."""
    path.mkdir(parents=True, exist_ok=True)

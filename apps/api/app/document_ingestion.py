from __future__ import annotations

from io import BytesIO
from zipfile import BadZipFile, ZipFile


PDF_MIME = "application/pdf"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
ALLOWED_RESUME_MIME_TYPES = frozenset((PDF_MIME, DOCX_MIME))


def detect_resume_mime_type(content: bytes) -> str | None:
    if content.startswith(b"%PDF-"):
        return PDF_MIME
    if not content.startswith(b"PK"):
        return None
    try:
        with ZipFile(BytesIO(content)) as archive:
            names = set(archive.namelist())
    except (BadZipFile, OSError):
        return None
    if "[Content_Types].xml" in names and "word/document.xml" in names:
        return DOCX_MIME
    return None


def safe_original_filename(filename: str | None, mime_type: str) -> str:
    fallback = "resume.pdf" if mime_type == PDF_MIME else "resume.docx"
    if not filename:
        return fallback
    basename = filename.replace("\\", "/").rsplit("/", 1)[-1]
    cleaned = "".join(
        character for character in basename if character.isprintable()
    ).strip()
    return cleaned[:255] or fallback


from __future__ import annotations

from io import BytesIO
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from pypdf import PdfReader

from .document_ingestion import DOCX_MIME, PDF_MIME


class DocumentParsingError(Exception):
    pass


class ResumeDocumentParser:
    """Deterministic PDF/DOCX parsing, independent of model interpretation."""

    def __init__(self, *, max_characters: int = 200_000, max_pages: int = 100) -> None:
        self._max_characters = max_characters
        self._max_pages = max_pages

    def extract(self, content: bytes, mime_type: str) -> str:
        if mime_type == PDF_MIME:
            text = self._extract_pdf(content)
        elif mime_type == DOCX_MIME:
            text = self._extract_docx(content)
        else:
            raise DocumentParsingError("unsupported resume type")
        cleaned = text.strip()
        if not cleaned:
            raise DocumentParsingError("resume contains no extractable text")
        if len(cleaned) > self._max_characters:
            raise DocumentParsingError(
                "extracted resume text exceeds the configured limit"
            )
        return cleaned

    def _extract_pdf(self, content: bytes) -> str:
        try:
            reader = PdfReader(BytesIO(content))
            if len(reader.pages) > self._max_pages:
                raise DocumentParsingError("resume has too many pages")
            pages = []
            for index, page in enumerate(reader.pages, start=1):
                page_text = (page.extract_text() or "").strip()
                if page_text:
                    pages.append(f"[Page {index}]\n{page_text}")
            return "\n\n".join(pages)
        except DocumentParsingError:
            raise
        except Exception as exc:
            raise DocumentParsingError("PDF text extraction failed") from exc

    def _extract_docx(self, content: bytes) -> str:
        try:
            with ZipFile(BytesIO(content)) as archive:
                info = archive.getinfo("word/document.xml")
                if info.file_size > self._max_characters * 20:
                    raise DocumentParsingError("DOCX document content is too large")
                root = ElementTree.fromstring(archive.read(info))
        except DocumentParsingError:
            raise
        except (BadZipFile, KeyError, ElementTree.ParseError, OSError) as exc:
            raise DocumentParsingError("DOCX text extraction failed") from exc

        namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        paragraphs: list[str] = []
        for paragraph in root.iter(f"{namespace}p"):
            fragments = [node.text or "" for node in paragraph.iter(f"{namespace}t")]
            text = "".join(fragments).strip()
            if text:
                paragraphs.append(f"[Paragraph {len(paragraphs) + 1}] {text}")
        return "\n".join(paragraphs)


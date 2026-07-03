"""Extract plain text from uploaded documents.

Supported formats: PDF, DOCX, TXT, PNG/JPG (via OCR if tesseract is available).
OCR failure is handled gracefully — returns empty string with a warning rather than
crashing, so other formats still work even without tesseract installed.
"""

import io
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_text_from_pdf(file_bytes: bytes) -> str:
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(file_bytes))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages).strip()
    except Exception as exc:
        logger.error("PDF extraction failed: %s", exc)
        return ""


def extract_text_from_docx(file_bytes: bytes) -> str:
    try:
        from docx import Document

        doc = Document(io.BytesIO(file_bytes))
        paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
        return "\n".join(paragraphs).strip()
    except Exception as exc:
        logger.error("DOCX extraction failed: %s", exc)
        return ""


def extract_text_from_image(file_bytes: bytes) -> str:
    try:
        import pytesseract
        from PIL import Image

        image = Image.open(io.BytesIO(file_bytes))
        text = pytesseract.image_to_string(image)
        return text.strip()
    except ImportError:
        logger.warning("pytesseract/Pillow not available — skipping OCR")
        return ""
    except Exception as exc:
        logger.error("Image OCR failed: %s", exc)
        return ""


def extract_text(file_bytes: bytes, filename: str) -> str:
    """Dispatch to the appropriate extractor based on file extension."""
    ext = Path(filename).suffix.lstrip(".").lower()

    dispatcher = {
        "pdf": extract_text_from_pdf,
        "docx": extract_text_from_docx,
        "txt": lambda b: b.decode("utf-8", errors="replace").strip(),
        "png": extract_text_from_image,
        "jpg": extract_text_from_image,
        "jpeg": extract_text_from_image,
    }

    handler = dispatcher.get(ext)
    if handler is None:
        logger.warning("No text extractor for extension '%s'", ext)
        return ""

    return handler(file_bytes)

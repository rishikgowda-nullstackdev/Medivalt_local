"""
MediVault Local - Ingestion Text Extractor (Person B)
Zero-cloud in-memory text extraction for PDF, TXT, and scanned image clinical records.
Supports scanned paper prescriptions & photographed lab slips via sovereign RapidOCR.
Uses BytesIO with PyMuPDF / pypdf - never writes temporary files to disk.
"""

from io import BytesIO
from pathlib import Path
from typing import Optional, Union

try:
    import pymupdf  # PyMuPDF (fitz)
except ImportError:
    pymupdf = None
import pypdf

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".tiff", ".bmp"}


def is_image_bytes(data: bytes) -> bool:
    """Detects common image magic headers in-memory."""
    if len(data) < 4:
        return False
    # PNG: \x89PNG\r\n\x1a\n
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return True
    # JPEG: \xff\xd8\xff
    if data.startswith(b"\xff\xd8\xff"):
        return True
    # WEBP: RIFF....WEBP
    if data.startswith(b"RIFF") and len(data) >= 12 and data[8:12] == b"WEBP":
        return True
    # BMP: BM
    if data.startswith(b"BM"):
        return True
    # TIFF: II*\x00 or MM\x00*
    if data.startswith(b"II*\x00") or data.startswith(b"MM\x00*"):
        return True
    return False


def _extract_from_pdf_bytes(pdf_bytes: bytes) -> str:
    """Extracts text from PDF bytes in-memory with PyMuPDF/pypdf and scanned OCR fallback."""
    text = ""
    # Try PyMuPDF first if installed
    if pymupdf is not None:
        try:
            with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
                pages = [page.get_text() for page in doc]
                text = "\n".join(p for p in pages if p).strip()
        except Exception:
            text = ""

    # Fallback to pypdf if PyMuPDF returned empty or failed
    if not text:
        try:
            reader = pypdf.PdfReader(BytesIO(pdf_bytes))
            pages = [p.extract_text() for p in reader.pages if p.extract_text()]
            text = "\n".join(pages).strip()
        except Exception as e:
            if not text:
                # If reading direct text failed, don't crash yet; might be scanned images
                pass

    # If extracted digital text is empty or sparse (< 15 chars), evaluate as scanned image PDF
    if len(text.strip()) < 15:
        try:
            from .ocr import is_ocr_available, extract_text_from_scanned_pdf
            if is_ocr_available():
                ocr_text = extract_text_from_scanned_pdf(pdf_bytes)
                if ocr_text and len(ocr_text.strip()) >= 10:
                    text = ocr_text
        except Exception:
            pass

    return text


def extract_text(file_source: Union[str, bytes, Path], filename: Optional[str] = None) -> str:
    """
    Extracts raw text from a PDF, TXT, or scanned image source (path or bytes).

    Args:
        file_source: File path (str/Path) or raw in-memory bytes.
        filename: Optional filename to hint the file extension when bytes are passed.

    Returns:
        Clean plain-text string extracted from the document.

    Raises:
        FileNotFoundError: If a file path is provided that does not exist.
        ValueError: If file type is unsupported, text is <10 chars, or >500KB.
    """
    raw_text = ""

    # Case 1: Raw bytes
    if isinstance(file_source, bytes):
        ext = Path(filename).suffix.lower() if filename else ""

        if ext in IMAGE_EXTENSIONS or (not ext and is_image_bytes(file_source)):
            from .ocr import extract_text_from_image_bytes
            raw_text = extract_text_from_image_bytes(file_source)
        elif ext == ".pdf" or (not ext and file_source.startswith(b"%PDF")):
            raw_text = _extract_from_pdf_bytes(file_source)
        elif ext in (".txt", ".text", ".md", ".json", ".hl7", ""):
            try:
                raw_text = file_source.decode("utf-8", errors="replace")
            except Exception as e:
                raise ValueError(f"Failed to decode text document: {str(e)}")
        else:
            allowed = ", ".join(sorted([".txt", ".pdf"] + list(IMAGE_EXTENSIONS)))
            raise ValueError(f"Unsupported file type '{ext}'. Allowed formats: {allowed}")

    # Case 2: File path (str or Path)
    elif isinstance(file_source, (str, Path)):
        path = Path(file_source)

        # Check if this is a path on disk
        if path.exists():
            ext = path.suffix.lower()
            if ext in IMAGE_EXTENSIONS:
                from .ocr import extract_text_from_image_bytes
                raw_text = extract_text_from_image_bytes(path.read_bytes())
            elif ext == ".txt" or ext in (".text", ".md", ".json", ".hl7"):
                raw_text = path.read_text(encoding="utf-8", errors="replace")
            elif ext == ".pdf":
                pdf_bytes = path.read_bytes()
                raw_text = _extract_from_pdf_bytes(pdf_bytes)
            else:
                allowed = ", ".join(sorted([".txt", ".pdf"] + list(IMAGE_EXTENSIONS)))
                raise ValueError(f"Unsupported file type '{ext}'. Allowed formats: {allowed}")
        else:
            # Check if it was intended as a filename / path or raw string
            ext = path.suffix.lower()
            all_known = {".txt", ".pdf", ".docx", ".doc", ".csv"} | IMAGE_EXTENSIONS
            if ext in all_known and (
                "\n" not in str(file_source)
                and len(str(file_source)) < 260
                and not any(w in str(file_source).lower() for w in ["patient", "doctor", "dr.", "rx", "diagnosis", "prescribe"])
            ):
                if ext not in ({".txt", ".pdf"} | IMAGE_EXTENSIONS):
                    allowed = ", ".join(sorted([".txt", ".pdf"] + list(IMAGE_EXTENSIONS)))
                    raise ValueError(f"Unsupported file type '{ext}'. Allowed formats: {allowed}")
                raise FileNotFoundError(f"File not found: {path}")

            # Otherwise, treat as raw text content directly
            raw_text = str(file_source)

    else:
        raise ValueError(f"Unsupported input type: {type(file_source).__name__}")

    # Guardrails: validate length
    if not raw_text or len(raw_text.strip()) < 10:
        raise ValueError("Uploaded document contains no readable text.")

    if len(raw_text) > 500_000:
        raise ValueError("Document exceeds maximum permitted size.")

    return raw_text.strip()

"""
MediVault Local - Ingestion Text Extractor (Person B)
Zero-cloud in-memory text extraction for PDF and TXT clinical records.
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


def _extract_from_pdf_bytes(pdf_bytes: bytes) -> str:
    """Extracts text from PDF bytes in-memory with PyMuPDF fallback to pypdf."""
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
                raise ValueError(f"Failed to parse PDF document: {str(e)}")

    return text


def extract_text(file_source: Union[str, bytes, Path], filename: Optional[str] = None) -> str:
    """
    Extracts raw text from a PDF or TXT source (path or bytes).

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

        if ext == ".pdf" or (not ext and file_source.startswith(b"%PDF")):
            raw_text = _extract_from_pdf_bytes(file_source)
        elif ext in (".txt", ""):
            try:
                raw_text = file_source.decode("utf-8", errors="replace")
            except Exception as e:
                raise ValueError(f"Failed to decode text document: {str(e)}")
        else:
            raise ValueError(f"Unsupported file type '{ext}'. Only .txt and .pdf are allowed.")

    # Case 2: File path (str or Path)
    elif isinstance(file_source, (str, Path)):
        path = Path(file_source)

        # Check if this is a path on disk
        if path.exists():
            ext = path.suffix.lower()
            if ext == ".txt":
                raw_text = path.read_text(encoding="utf-8", errors="replace")
            elif ext == ".pdf":
                pdf_bytes = path.read_bytes()
                raw_text = _extract_from_pdf_bytes(pdf_bytes)
            else:
                raise ValueError(f"Unsupported file type '{ext}'. Only .txt and .pdf are allowed.")
        else:
            # Check if it was intended as a filename / path or raw string
            # If it has a file extension or looks like a file path:
            ext = path.suffix.lower()
            if ext in (".txt", ".pdf", ".docx", ".doc", ".png", ".jpg", ".csv") and ("\n" not in str(file_source) and len(str(file_source)) < 260 and not any(w in str(file_source).lower() for w in ["patient", "doctor", "dr.", "rx", "diagnosis", "prescribe"])):
                if ext not in (".txt", ".pdf"):
                    raise ValueError(f"Unsupported file type '{ext}'. Only .txt and .pdf are allowed.")
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

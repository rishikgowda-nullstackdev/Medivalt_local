"""
MediVault Local - Offline OCR Engine (Person B)
Zero-cloud on-device optical character recognition for scanned paper prescriptions,
photographed clinical notes, and image-based lab records.
Uses RapidOCR (ONNX Runtime) + Pillow. Runs 100% offline on CPU with zero network egress.
"""

import io
import logging
from typing import Optional, List, Tuple
from pathlib import Path

logger = logging.getLogger("medivault.ingestion.ocr")

_OCR_ENGINE = None


def is_ocr_available() -> bool:
    """Checks whether local ONNX OCR dependencies (RapidOCR and PIL) are available."""
    try:
        from rapidocr_onnxruntime import RapidOCR
        from PIL import Image
        import numpy as np
        return True
    except ImportError:
        return False


def get_ocr_engine():
    """
    Returns a process-wide singleton RapidOCR instance.
    Lazy-loads ONNX models once in memory for ultra-fast sub-second subsequent inferences.
    """
    global _OCR_ENGINE
    if _OCR_ENGINE is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
            # RapidOCR default configuration runs local CPU inference with zero network egress
            _OCR_ENGINE = RapidOCR()
            logger.info("RapidOCR sovereign engine initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize RapidOCR engine: {e}")
            raise RuntimeError(f"Local OCR engine initialization failed: {str(e)}")
    return _OCR_ENGINE


def extract_text_from_image_bytes(image_bytes: bytes) -> str:
    """
    Extracts text from raw image bytes (.png, .jpg, .jpeg, .webp, .tiff, .bmp)
    using the sovereign on-device RapidOCR model.

    Args:
        image_bytes: Raw binary content of the image.

    Returns:
        Extracted plain text formatted by visual lines.

    Raises:
        ValueError: If image is corrupt or unreadable.
    """
    if not image_bytes or len(image_bytes) == 0:
        raise ValueError("Image bytes are empty (0 bytes).")

    try:
        from PIL import Image
        import numpy as np
    except ImportError as e:
        raise RuntimeError(f"OCR dependencies not installed: {str(e)}")

    try:
        # Load and normalize image
        with Image.open(io.BytesIO(image_bytes)) as pil_img:
            # Convert palette/RGBA/grayscale to standard 3-channel RGB for ONNX input
            if pil_img.mode != "RGB":
                rgb_img = pil_img.convert("RGB")
            else:
                rgb_img = pil_img.copy()

            img_np = np.array(rgb_img)
    except Exception as e:
        raise ValueError(f"Failed to decode image file: {str(e)}")

    ocr = get_ocr_engine()
    try:
        results, elapse_list = ocr(img_np)
    except Exception as e:
        raise ValueError(f"OCR text extraction failed on image: {str(e)}")

    if not results:
        return ""

    # Each result row in RapidOCR: [box_coordinates, text_line, confidence_score]
    lines: List[str] = []
    for item in results:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            line_text = str(item[1]).strip()
            if line_text:
                lines.append(line_text)

    return "\n".join(lines).strip()


def extract_text_from_scanned_pdf(pdf_bytes: bytes) -> str:
    """
    Extracts text from an image-only scanned PDF document.
    Inspects embedded page images in-memory and executes OCR page by page.

    Args:
        pdf_bytes: Raw PDF bytes.

    Returns:
        Consolidated plain text extracted across all scanned pages.
    """
    if not pdf_bytes or len(pdf_bytes) == 0:
        raise ValueError("PDF bytes are empty (0 bytes).")

    extracted_pages: List[str] = []

    # Strategy A: Check PyMuPDF if available (fastest pixmap rendering)
    try:
        import pymupdf
        with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
            for page_idx in range(len(doc)):
                page = doc[page_idx]
                # Render full page raster at 200 DPI
                pix = page.get_pixmap(dpi=200)
                png_bytes = pix.tobytes("png")
                page_text = extract_text_from_image_bytes(png_bytes)
                if page_text:
                    extracted_pages.append(page_text)
    except Exception:
        extracted_pages = []

    # Strategy B: Fallback to pypdf embedded image extraction
    if not extracted_pages:
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
            for page_idx, page in enumerate(reader.pages):
                page_text_pieces: List[str] = []
                # Check embedded raster images in page
                if hasattr(page, "images") and page.images:
                    for img_obj in page.images:
                        try:
                            img_data = img_obj.data
                            txt = extract_text_from_image_bytes(img_data)
                            if txt:
                                page_text_pieces.append(txt)
                        except Exception as e:
                            logger.warning(f"Failed to OCR embedded PDF image: {e}")
                
                if page_text_pieces:
                    extracted_pages.append("\n".join(page_text_pieces))
        except Exception as e:
            logger.warning(f"pypdf scanned image fallback failed: {e}")

    return "\n\n".join(extracted_pages).strip()

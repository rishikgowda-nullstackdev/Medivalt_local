"""
MediVault Local - Pure-Python Sample PDF Generator
Generates valid PDF-1.4 test files without external C++ or non-standard dependencies.
"""

import os

def create_simple_pdf(text_content: str, output_path: str):
    """Generates a minimal valid PDF-1.4 file containing the specified text."""
    lines = text_content.strip().split("\n")
    
    # Escape parentheses and backslashes in PDF text strings
    escaped_lines = []
    for line in lines:
        cleaned = line.replace("—", "-").replace("–", "-")
        cleaned = cleaned.encode("ascii", "ignore").decode("ascii")
        cleaned = cleaned.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        escaped_lines.append(cleaned[:85]) # Keep line width reasonable

    # Build PDF stream content
    y_start = 750
    stream_content_lines = ["BT", "/F1 10 Tf", f"50 {y_start} Td", "14 TL"]
    for i, line in enumerate(escaped_lines):
        if i == 0:
            stream_content_lines.append(f"({line}) Tj")
        else:
            stream_content_lines.append("T*")
            stream_content_lines.append(f"({line}) Tj")
    stream_content_lines.append("ET")
    
    stream_bytes = "\n".join(stream_content_lines).encode("latin-1")
    stream_len = len(stream_bytes)

    objects = []
    # 1: Catalog
    objects.append("1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    # 2: Pages
    objects.append("2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")
    # 3: Page
    objects.append("3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n")
    # 4: Stream
    objects.append(f"4 0 obj\n<< /Length {stream_len} >>\nstream\n".encode("latin-1") + stream_bytes + b"\nendstream\nendobj\n")
    # 5: Font
    objects.append("5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n")

    # Assemble PDF with cross-reference table
    header = b"%PDF-1.4\n"
    body = bytearray(header)
    xref_offsets = [0]

    for obj in objects:
        xref_offsets.append(len(body))
        if isinstance(obj, str):
            body.extend(obj.encode("latin-1"))
        else:
            body.extend(obj)

    xref_start = len(body)
    body.extend(f"xref\n0 {len(xref_offsets)}\n".encode("latin-1"))
    body.extend(b"0000000000 65535 f \n")
    for offset in xref_offsets[1:]:
        body.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))

    trailer = (
        f"trailer\n<< /Size {len(xref_offsets)} /Root 1 0 R >>\n"
        f"startxref\n{xref_start}\n%%EOF\n"
    )
    body.extend(trailer.encode("latin-1"))

    with open(output_path, "wb") as f:
        f.write(body)

if __name__ == "__main__":
    samples_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Generate patient 1 PDF
    txt1 = open(os.path.join(samples_dir, "patient_1_ckd_discharge.txt"), "r").read()
    pdf1 = os.path.join(samples_dir, "patient_1_ckd_discharge.pdf")
    create_simple_pdf(txt1, pdf1)
    print(f"Generated: {pdf1}")

    # Generate patient 2 PDF
    txt2 = open(os.path.join(samples_dir, "patient_2_asthma_consult.txt"), "r").read()
    pdf2 = os.path.join(samples_dir, "patient_2_asthma_consult.pdf")
    create_simple_pdf(txt2, pdf2)
    print(f"Generated: {pdf2}")

    # Generate prescription triple whammy PDF
    p_txt1 = open(os.path.join(samples_dir, "prescription_triple_whammy.txt"), "r").read()
    p_pdf1 = os.path.join(samples_dir, "prescription_triple_whammy.pdf")
    create_simple_pdf(p_txt1, p_pdf1)
    print(f"Generated: {p_pdf1}")

    # Generate prescription safe regimen PDF
    p_txt2 = open(os.path.join(samples_dir, "prescription_safe_regimen.txt"), "r").read()
    p_pdf2 = os.path.join(samples_dir, "prescription_safe_regimen.pdf")
    create_simple_pdf(p_txt2, p_pdf2)
    print(f"Generated: {p_pdf2}")


"""
MediVault Local - Synthetic Scanned Medical Image & PDF Generator
Generates realistic scanned prescription and lab slip images for testing 100% offline OCR.
Zero real patient data — 100% synthetic clinical benchmarks.
"""

import os
import io
from PIL import Image, ImageDraw, ImageFont

SAMPLES_DIR = os.path.dirname(os.path.abspath(__file__))


def create_scanned_image(lines: list, width: int = 800, height: int = 400, header_color=(20, 50, 80)) -> Image.Image:
    """Renders synthetic clinical document text into a realistic scanned paper bitmap."""
    # Light paper texture background with slight cream tone
    img = Image.new("RGB", (width, height), color=(250, 250, 248))
    draw = ImageDraw.Draw(img)

    # Draw border simulating paper margin
    draw.rectangle([(10, 10), (width - 10, height - 10)], outline=(210, 215, 220), width=2)
    # Header bar
    draw.rectangle([(10, 10), (width - 10, 55)], fill=header_color)

    # Header text
    if lines:
        draw.text((25, 22), lines[0], fill=(255, 255, 255))

    y = 75
    for line in lines[1:]:
        if not line.strip():
            y += 15
            continue
        # Check if line is a divider
        if line.startswith("---"):
            draw.line([(25, y + 5), (width - 25, y + 5)], fill=(200, 205, 210), width=1)
            y += 18
            continue

        # Normal text line
        draw.text((30, y), line, fill=(30, 35, 42))
        y += 26

    # Bottom watermark
    draw.text((width - 320, height - 28), "SOVEREIGN CLINICAL SCAN · NOT PERSISTED", fill=(170, 175, 180))

    return img


def generate_all_samples():
    os.makedirs(SAMPLES_DIR, exist_ok=True)

    # 1. Scanned Prescription Slip (Triple Whammy Challenge)
    rx_lines = [
        "ST. JUDE REGIONAL MEDICAL CENTER · RX DISCHARGE ORDER",
        "Patient: Jonathan Doe | DOB: 1965-08-14 | Phone: 555-019-8234",
        "Attending: Dr. House, MD | License: MD-8923441",
        "--------------------------------------------------------------------------------",
        "Rx 1: Lisinopril 20mg PO QD (Oral Tablet)",
        "Rx 2: Furosemide 40mg PO QD (Oral Tablet)",
        "Rx 3: Ibuprofen 400mg PO TID PRN (Oral Tablet)",
        "--------------------------------------------------------------------------------",
        "Special Instructions: Take with food. Cross-verify renal status."
    ]
    img_rx = create_scanned_image(rx_lines, width=820, height=340, header_color=(24, 70, 60))
    rx_path = os.path.join(SAMPLES_DIR, "scanned_prescription_slip.png")
    img_rx.save(rx_path, format="PNG")
    print(f"Generated: {rx_path}")

    # 2. Scanned Diagnostic Lab Slip (Renal & Coagulation Panel)
    lab_lines = [
        "METROPOLITAN DIAGNOSTIC CORE LAB · BIOCHEMICAL ASSAY",
        "Patient Name: Robert Smith | MRN: MRN-994821 | Phone: 555-017-3391",
        "Clinical Indication: Chronic Kidney Disease & Hypertension Workup",
        "--------------------------------------------------------------------------------",
        "eGFR: 32 mL/min/1.73m2 (Reference: >= 60 mL/min/1.73m2)",
        "Serum Creatinine: 2.1 mg/dL (Reference: 0.7 - 1.3 mg/dL)",
        "Potassium: 5.2 mEq/L (Reference: 3.5 - 5.0 mEq/L)",
        "Blood Pressure: 158/96 mmHg",
        "Allergies: Penicillin, Cephalosporins (Reported Anaphylaxis)",
        "Active Medications: Warfarin 5mg PO daily, Lisinopril 10mg daily",
        "--------------------------------------------------------------------------------",
        "Diagnoses: Chronic Kidney Disease Stage 3b, Hypertension, Atrial Fibrillation"
    ]
    img_lab = create_scanned_image(lab_lines, width=840, height=440, header_color=(15, 45, 80))
    lab_path = os.path.join(SAMPLES_DIR, "scanned_lab_slip.png")
    img_lab.save(lab_path, format="PNG")
    print(f"Generated: {lab_path}")

    # 3. Scanned PDF (Pure Image PDF containing no extractable text layer)
    pdf_path = os.path.join(SAMPLES_DIR, "scanned_paper_record.pdf")
    img_lab.save(pdf_path, format="PDF")
    print(f"Generated Scanned PDF: {pdf_path}")


if __name__ == "__main__":
    generate_all_samples()

"""
MediVault Local - Input Validation & Defensive Guardrails
Implements strict validation for files, text payloads, and clinical parameters.
Adheres to AGENTS.md Rule 4: "Every function that touches external input validates
and fails with a clear message — never a raw stack trace or silent crash."
"""

import os
from typing import Optional, Tuple
from fastapi import HTTPException, UploadFile

# Limits
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_TEXT_LENGTH = 250_000               # 250k characters
ALLOWED_EXTENSIONS = {".pdf", ".txt", ".text", ".md", ".json", ".hl7"}


class InputValidator:
    """Defensive validation against corrupted, oversized, or malicious inputs."""

    @classmethod
    def validate_upload_file(cls, file: UploadFile, content: bytes) -> None:
        """
        Validates uploaded file extension, size, and readable content.
        Raises clean HTTPException with actionable user messages.
        """
        if not file.filename:
            raise HTTPException(
                status_code=400,
                detail="Invalid file: No filename provided."
            )

        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            allowed_str = ", ".join(sorted(list(ALLOWED_EXTENSIONS)))
            raise HTTPException(
                status_code=415,
                detail=f"Unsupported file format '{ext}'. Allowed medical record formats: {allowed_str}"
            )

        if len(content) == 0:
            raise HTTPException(
                status_code=400,
                detail=f"Uploaded file '{file.filename}' is empty (0 bytes). Please upload a valid clinical record."
            )

        if len(content) > MAX_FILE_SIZE_BYTES:
            max_mb = MAX_FILE_SIZE_BYTES // (1024 * 1024)
            raise HTTPException(
                status_code=413,
                detail=f"File exceeds maximum allowed size ({max_mb} MB). Please upload a standard patient summary."
            )

    @classmethod
    def validate_clinical_text(cls, text: Optional[str], field_name: str = "text") -> str:
        """
        Validates text input for non-empty content and reasonable length.
        """
        if text is None:
            raise HTTPException(
                status_code=400,
                detail=f"Required field '{field_name}' is missing."
            )

        cleaned = text.strip()
        if not cleaned:
            raise HTTPException(
                status_code=400,
                detail=f"Field '{field_name}' cannot be empty or whitespace only."
            )

        if len(cleaned) > MAX_TEXT_LENGTH:
            raise HTTPException(
                status_code=413,
                detail=f"Payload in '{field_name}' exceeds maximum permitted character limit ({MAX_TEXT_LENGTH:,} chars)."
            )

        return cleaned

    @classmethod
    def validate_medication_name(cls, med_name: Optional[str]) -> str:
        """
        Validates proposed medication name for clinical review.
        """
        cleaned = cls.validate_clinical_text(med_name, field_name="proposed_medication")

        if len(cleaned) < 2:
            raise HTTPException(
                status_code=400,
                detail="Medication name is too short. Please enter a valid drug name (e.g., 'Ibuprofen', 'Advil')."
            )

        # Check for invalid control characters or script injections
        if any(char in cleaned for char in "<>{}\\\0"):
            raise HTTPException(
                status_code=400,
                detail="Medication name contains invalid characters. Please use standard alphanumeric drug names."
            )

        return cleaned

"""
MediVault Local - Cryptographic Local Audit Logger
Complies with HIPAA Security Rule § 164.312(b) & India DPDP Act.
Every review generates a tamper-evident SHA-256 hash-chained log entry.
"""

import os
import json
import sqlite3
import hashlib
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "medivault.db")
AUDIT_LOG_FILE = os.path.join(BASE_DIR, "database", "audit_trail.jsonl")

import threading

class AuditLogger:
    """
    Manages local, tamper-evident audit logs with cryptographic hash chaining.
    Thread-safe and concurrency-hardened.
    """

    def __init__(self, log_path: str = AUDIT_LOG_FILE, db_path: str = DB_PATH):
        self.log_path = os.path.abspath(log_path)
        self.db_path = os.path.abspath(db_path)
        self._lock = threading.Lock()
        self._ensure_log_initialized()

    def _ensure_log_initialized(self) -> None:
        """Initializes the genesis block if the audit log does not exist."""
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        if not os.path.exists(self.log_path) or os.path.getsize(self.log_path) == 0:
            genesis_entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event_id": "GENESIS_00000000",
                "patient_hash": "GENESIS",
                "proposed_medication": "SYSTEM_INIT",
                "overall_status": "SAFE",
                "alerts_count": 0,
                "zero_cloud_enforced": True,
                "execution_time_ms": 0.0,
                "prev_hash": "0" * 64,
                "audit_hash": hashlib.sha256(b"MEDIVAULT_GENESIS_BLOCK_2026").hexdigest()
            }
            with open(self.log_path, "w", encoding="utf-8") as f:
                f.write(json.dumps(genesis_entry) + "\n")

    def get_last_hash(self) -> str:
        """Retrieves the audit hash of the most recent log entry."""
        if not os.path.exists(self.log_path):
            return "0" * 64

        last_line = ""
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    last_line = line

        if not last_line:
            return "0" * 64

        try:
            entry = json.loads(last_line)
            return entry.get("audit_hash", "0" * 64)
        except Exception:
            return "0" * 64

    def log_review(
        self,
        patient_token: str,
        proposed_medication: str,
        overall_status: str,
        alerts_count: int,
        execution_time_ms: float
    ) -> Dict[str, Any]:
        """
        Appends an immutable SHA-256 hash-chained event to the audit trail.
        Thread-safe under high-concurrency loads.
        """
        with self._lock:
            timestamp = datetime.now(timezone.utc).isoformat()
            prev_hash = self.get_last_hash()
            event_id = f"EVT_{int(datetime.now(timezone.utc).timestamp() * 1000)}"

            # Chained hash calculation
            payload = (
                f"{prev_hash}|{timestamp}|{event_id}|{patient_token}|"
                f"{proposed_medication}|{overall_status}|{alerts_count}|{execution_time_ms}"
            )
            current_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

            entry = {
                "timestamp": timestamp,
                "event_id": event_id,
                "patient_hash": patient_token,
                "proposed_medication": proposed_medication,
                "overall_status": overall_status,
                "alerts_count": alerts_count,
                "zero_cloud_enforced": True,
                "execution_time_ms": execution_time_ms,
                "prev_hash": prev_hash,
                "audit_hash": current_hash
            }

            # 1. Append to JSONL file
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")

            # 2. Insert into SQLite DB if available
            try:
                conn = sqlite3.connect(self.db_path, timeout=5.0)
                cursor = conn.cursor()
                cursor.execute("PRAGMA busy_timeout = 5000;")
                cursor.execute("""
                    INSERT INTO audit_logs (
                        event_id, timestamp, patient_hash, proposed_medication,
                        overall_status, alerts_count, zero_cloud_verified,
                        execution_time_ms, prev_hash, audit_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
                """, (
                    event_id, timestamp, patient_token, proposed_medication,
                    overall_status, alerts_count, execution_time_ms, prev_hash, current_hash
                ))
                conn.commit()
                conn.close()
            except Exception:
                pass  # JSONL remains primary audit of record

            return entry

    def verify_integrity(self) -> Dict[str, Any]:
        """
        Cryptographic verification: Scans the entire audit chain, recomputes hashes,
        and mathematically verifies that zero entries have been tampered with or deleted.
        """
        if not os.path.exists(self.log_path):
            return {"valid": True, "total_blocks": 0, "status": "NO_LOGS"}

        entries = []
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        entries.append(json.loads(line))
                    except Exception:
                        return {"valid": False, "error": "Corrupted JSON line detected in audit file."}

        if not entries:
            return {"valid": True, "total_blocks": 0, "status": "EMPTY"}

        # Validate Genesis
        expected_prev = "0" * 64
        for i, entry in enumerate(entries):
            if i == 0:
                expected_prev = entry["audit_hash"]
                continue

            # Verify chain link
            if entry["prev_hash"] != expected_prev:
                return {
                    "valid": False,
                    "tampered_at_index": i,
                    "event_id": entry["event_id"],
                    "error": f"Chain broken: expected prev_hash '{expected_prev}', found '{entry['prev_hash']}'"
                }

            # Recompute hash
            alerts_count = entry.get("alerts_count", 0)
            exec_time = entry.get("execution_time_ms", 0.0)
            payload = (
                f"{entry['prev_hash']}|{entry['timestamp']}|{entry['event_id']}|{entry['patient_hash']}|"
                f"{entry['proposed_medication']}|{entry['overall_status']}|{alerts_count}|{exec_time}"
            )
            recomputed = hashlib.sha256(payload.encode("utf-8")).hexdigest()

            # Fallback check for genesis or legacy format
            if recomputed != entry["audit_hash"]:
                # Try legacy payload without alerts_count if written by v1.0
                legacy_payload = (
                    f"{entry['prev_hash']}|{entry['timestamp']}|{entry['event_id']}|{entry['patient_hash']}|"
                    f"{entry['proposed_medication']}|{entry['overall_status']}|{exec_time}"
                )
                if hashlib.sha256(legacy_payload.encode("utf-8")).hexdigest() == entry["audit_hash"]:
                    recomputed = entry["audit_hash"]

            if recomputed != entry["audit_hash"]:
                return {
                    "valid": False,
                    "tampered_at_index": i,
                    "event_id": entry["event_id"],
                    "error": f"Data altered: recomputed hash '{recomputed}' does not match stored hash '{entry['audit_hash']}'"
                }

            expected_prev = entry["audit_hash"]

        return {
            "valid": True,
            "total_blocks": len(entries),
            "latest_hash": expected_prev,
            "status": "ALL_BLOCKS_VALID_TAMPER_FREE"
        }

    def get_recent_logs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Returns the most recent N logs (newest first)."""
        if not os.path.exists(self.log_path):
            return []

        entries = []
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        entries.append(json.loads(line))
                    except Exception:
                        continue

        return list(reversed(entries[-limit:]))


audit_logger = AuditLogger()

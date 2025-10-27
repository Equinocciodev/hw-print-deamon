"""
Persistent print job store backed by SQLite.
Tracks job lifecycle, printer state, retries, and recovery metadata.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    """Return current UTC time."""
    return datetime.utcnow()


def _iso(dt: Optional[datetime]) -> Optional[str]:
    """Convert datetime to ISO8601 string."""
    return dt.isoformat(timespec="seconds") if dt else None


@dataclass(frozen=True)
class JobRecord:
    """Representation of a job row fetched from the store."""

    id: str
    printer_name: str
    orientation: str
    status: str
    attempts: int
    max_attempts: int
    sequence_number: int
    external_sequence: Optional[str]
    payload: str
    pdf_file: Optional[str]
    pages: Optional[int]
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    available_at: Optional[datetime]
    verification_status: Optional[str]
    verification_message: Optional[str]
    metadata: Optional[Dict[str, Any]]


class JobStore:
    """SQLite-backed job persistence component."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._lock = threading.RLock()
        self._ensure_directory()
        self._initialize()

    def _ensure_directory(self) -> None:
        base_dir = os.path.dirname(self.db_path)
        if base_dir and not os.path.exists(base_dir):
            os.makedirs(base_dir, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    @contextmanager
    def _cursor(self):
        with self._lock:
            conn = self._connect()
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def _initialize(self) -> None:
        with self._cursor() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS print_jobs (
                    id TEXT PRIMARY KEY,
                    printer_name TEXT NOT NULL,
                    orientation TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    max_attempts INTEGER NOT NULL DEFAULT 3,
                    sequence_number INTEGER NOT NULL,
                    external_sequence TEXT,
                    payload TEXT NOT NULL,
                    pdf_file TEXT,
                    pages INTEGER,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    available_at TEXT,
                    verification_status TEXT DEFAULT 'pending',
                    verification_message TEXT,
                    metadata TEXT
                );
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS printer_state (
                    printer_name TEXT PRIMARY KEY,
                    last_sequence_processed INTEGER NOT NULL DEFAULT 0,
                    paused INTEGER NOT NULL DEFAULT 0,
                    pause_reason TEXT,
                    updated_at TEXT NOT NULL,
                    last_error_at TEXT
                );
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS job_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    printer_name TEXT NOT NULL,
                    event TEXT NOT NULL,
                    detail TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(job_id) REFERENCES print_jobs(id) ON DELETE CASCADE
                );
                """
            )

            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_print_jobs_printer_status "
                "ON print_jobs(printer_name, status, sequence_number);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_print_jobs_available_at "
                "ON print_jobs(status, available_at);"
            )

    def _row_to_record(self, row: sqlite3.Row) -> JobRecord:
        def _parse(dt_value: Optional[str]) -> Optional[datetime]:
            return datetime.fromisoformat(dt_value) if dt_value else None

        metadata = None
        if row["metadata"]:
            try:
                metadata = json.loads(row["metadata"])
            except json.JSONDecodeError:
                metadata = {"raw": row["metadata"], "error": "invalid-json"}

        return JobRecord(
            id=row["id"],
            printer_name=row["printer_name"],
            orientation=row["orientation"],
            status=row["status"],
            attempts=row["attempts"],
            max_attempts=row["max_attempts"],
            sequence_number=row["sequence_number"],
            external_sequence=row["external_sequence"],
            payload=row["payload"],
            pdf_file=row["pdf_file"],
            pages=row["pages"],
            error_message=row["error_message"],
            created_at=_parse(row["created_at"]),
            updated_at=_parse(row["updated_at"]),
            started_at=_parse(row["started_at"]),
            completed_at=_parse(row["completed_at"]),
            available_at=_parse(row["available_at"]),
            verification_status=row["verification_status"],
            verification_message=row["verification_message"],
            metadata=metadata,
        )

    def _insert_event(
        self, conn: sqlite3.Connection, job_id: str, printer_name: str, event: str, detail: Optional[str] = None
    ) -> None:
        conn.execute(
            """
            INSERT INTO job_events(job_id, printer_name, event, detail, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (job_id, printer_name, event, detail, _iso(_utcnow())),
        )

    def _ensure_printer_state(self, conn: sqlite3.Connection, printer_name: str) -> None:
        conn.execute(
            """
            INSERT INTO printer_state(printer_name, updated_at)
            VALUES(?, ?)
            ON CONFLICT(printer_name) DO NOTHING
            """,
            (printer_name, _iso(_utcnow())),
        )

    # Public API -----------------------------------------------------------------

    def enqueue_job(
        self,
        job_id: str,
        printer_name: str,
        orientation: str,
        payload: str,
        external_sequence: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        max_attempts: int = 3,
    ) -> JobRecord:
        """Persist a new job and return its record."""
        now = _utcnow()
        metadata_json = json.dumps(metadata) if metadata else None

        with self._cursor() as conn:
            conn.execute("BEGIN IMMEDIATE;")
            self._ensure_printer_state(conn, printer_name)

            sequence = conn.execute(
                """
                SELECT COALESCE(MAX(sequence_number), 0) + 1
                FROM print_jobs
                WHERE printer_name = ?
                """,
                (printer_name,),
            ).fetchone()[0]

            conn.execute(
                """
                INSERT INTO print_jobs(
                    id, printer_name, orientation, status, attempts, max_attempts,
                    sequence_number, external_sequence, payload, created_at, updated_at,
                    available_at, metadata
                )
                VALUES(?, ?, ?, 'queued', 0, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    printer_name,
                    orientation,
                    max_attempts,
                    sequence,
                    external_sequence,
                    payload,
                    _iso(now),
                    _iso(now),
                    _iso(now),
                    metadata_json,
                ),
            )

            self._insert_event(conn, job_id, printer_name, "queued", f"seq={sequence}")

            row = conn.execute(
                "SELECT * FROM print_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()

        logger.info("Persisted job %s for printer %s (seq #%s)", job_id, printer_name, sequence)
        return self._row_to_record(row)

    def fetch_next_job(self, printer_name: str) -> Optional[JobRecord]:
        """Fetch and lock the next available job for processing."""
        now = _utcnow()
        now_iso = _iso(now)

        with self._cursor() as conn:
            conn.execute("BEGIN IMMEDIATE;")
            state = conn.execute(
                "SELECT paused, pause_reason FROM printer_state WHERE printer_name = ?",
                (printer_name,),
            ).fetchone()

            if state and state["paused"]:
                return None

            row = conn.execute(
                """
                SELECT *
                FROM print_jobs
                WHERE printer_name = ?
                  AND status IN ('queued', 'retry_waiting')
                  AND (available_at IS NULL OR available_at <= ?)
                  AND attempts < max_attempts
                ORDER BY sequence_number ASC, created_at ASC
                LIMIT 1
                """,
                (printer_name, now_iso),
            ).fetchone()

            if not row:
                return None

            job_id = row["id"]
            attempts = row["attempts"] + 1
            conn.execute(
                """
                UPDATE print_jobs
                SET status = 'processing',
                    attempts = ?,
                    started_at = ?,
                    updated_at = ?,
                    available_at = NULL
                WHERE id = ?
                """,
                (attempts, now_iso, now_iso, job_id),
            )

            self._insert_event(conn, job_id, printer_name, "processing", f"attempt={attempts}")

            row = conn.execute("SELECT * FROM print_jobs WHERE id = ?", (job_id,)).fetchone()

        return self._row_to_record(row) if row else None

    def mark_job_printing(self, job_id: str) -> None:
        """Update a job status to printing (spooled)."""
        now_iso = _iso(_utcnow())
        with self._cursor() as conn:
            conn.execute(
                """
                UPDATE print_jobs
                SET status = 'printing',
                    updated_at = ?
                WHERE id = ?
                """,
                (now_iso, job_id),
            )

            row = conn.execute(
                "SELECT printer_name FROM print_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()

            if row:
                self._insert_event(conn, job_id, row["printer_name"], "printing")

    def mark_job_completed(
        self,
        job_id: str,
        *,
        pdf_file: Optional[str] = None,
        pages: Optional[int] = None,
        verification_message: Optional[str] = None,
    ) -> None:
        """Mark job as completed and update printer state."""
        now = _utcnow()
        now_iso = _iso(now)

        with self._cursor() as conn:
            row = conn.execute(
                "SELECT printer_name, sequence_number FROM print_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()

            if not row:
                logger.warning("Attempted to complete unknown job %s", job_id)
                return

            printer_name = row["printer_name"]
            sequence_number = row["sequence_number"]

            conn.execute(
                """
                UPDATE print_jobs
                SET status = 'completed',
                    pdf_file = COALESCE(?, pdf_file),
                    pages = COALESCE(?, pages),
                    completed_at = ?,
                    updated_at = ?,
                    verification_status = 'verified',
                    verification_message = ?
                WHERE id = ?
                """,
                (pdf_file, pages, now_iso, now_iso, verification_message, job_id),
            )

            conn.execute(
                """
                UPDATE printer_state
                SET last_sequence_processed = ?,
                    paused = 0,
                    pause_reason = NULL,
                    updated_at = ?
                WHERE printer_name = ?
                """,
                (sequence_number, now_iso, printer_name),
            )

            self._insert_event(conn, job_id, printer_name, "completed", verification_message)

    def mark_job_failed(
        self,
        job_id: str,
        *,
        error: str,
        retry_delay: int = 60,
    ) -> Dict[str, Any]:
        """
        Mark job as failed. If attempts remain schedule retry, otherwise pause the printer.
        Returns structured result containing status and pause flag.
        """
        now = _utcnow()
        now_iso = _iso(now)
        next_available = _iso(now + timedelta(seconds=retry_delay))

        with self._cursor() as conn:
            row = conn.execute(
                "SELECT * FROM print_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()

            if not row:
                logger.warning("Attempted to fail unknown job %s", job_id)
                return {"status": "missing"}

            printer_name = row["printer_name"]
            attempts = row["attempts"]
            max_attempts = row["max_attempts"]
            sequence_number = row["sequence_number"]

            if attempts >= max_attempts:
                conn.execute(
                    """
                    UPDATE print_jobs
                    SET status = 'failed',
                        error_message = ?,
                        updated_at = ?,
                        completed_at = ?,
                        verification_status = 'failed',
                        verification_message = ?
                    WHERE id = ?
                    """,
                    (error, now_iso, now_iso, error, job_id),
                )

                conn.execute(
                    """
                    UPDATE printer_state
                    SET paused = 1,
                        pause_reason = ?,
                        updated_at = ?,
                        last_error_at = ?
                    WHERE printer_name = ?
                    """,
                    (f"Job {job_id} failed after {attempts} attempts", now_iso, now_iso, printer_name),
                )

                detail = f"failed after {attempts} attempts (seq #{sequence_number})"
                self._insert_event(conn, job_id, printer_name, "failed", detail)

                return {
                    "status": "failed",
                    "paused": True,
                    "attempts": attempts,
                    "max_attempts": max_attempts,
                }

            conn.execute(
                """
                UPDATE print_jobs
                SET status = 'retry_waiting',
                    error_message = ?,
                    updated_at = ?,
                    available_at = ?
                WHERE id = ?
                """,
                (error, now_iso, next_available, job_id),
            )

            detail = f"retry scheduled in {retry_delay}s (attempt {attempts}/{max_attempts})"
            self._insert_event(conn, job_id, printer_name, "retry_scheduled", detail)

            return {
                "status": "retry_scheduled",
                "paused": False,
                "attempts": attempts,
                "max_attempts": max_attempts,
                "retry_at": next_available,
            }

    def recover_stuck_jobs(self, printer_name: str) -> None:
        """
        Reset in-flight jobs for a printer to queued so they can resume after crashes.
        """
        now_iso = _iso(_utcnow())
        with self._cursor() as conn:
            rows = conn.execute(
                """
                SELECT id FROM print_jobs
                WHERE printer_name = ?
                  AND status IN ('processing', 'printing')
                """,
                (printer_name,),
            ).fetchall()

            if not rows:
                return

            job_ids = [row["id"] for row in rows]
            logger.warning(
                "Recovering %d stuck jobs for printer %s: %s",
                len(job_ids),
                printer_name,
                ", ".join(job_ids),
            )

            conn.execute(
                f"""
                UPDATE print_jobs
                SET status = 'queued',
                    updated_at = ?,
                    started_at = NULL,
                    completed_at = NULL,
                    available_at = ?
                WHERE id IN ({','.join(['?'] * len(job_ids))})
                """,
                (now_iso, now_iso, *job_ids),
            )

            for job_id in job_ids:
                self._insert_event(conn, job_id, printer_name, "recovered")

    def get_printer_state(self, printer_name: str) -> Dict[str, Any]:
        """Return current printer state summary."""
        with self._cursor() as conn:
            state = conn.execute(
                "SELECT * FROM printer_state WHERE printer_name = ?",
                (printer_name,),
            ).fetchone()

            if not state:
                return {
                    "printer_name": printer_name,
                    "paused": False,
                    "pause_reason": None,
                    "last_sequence_processed": 0,
                }

            return {
                "printer_name": printer_name,
                "paused": bool(state["paused"]),
                "pause_reason": state["pause_reason"],
                "last_sequence_processed": state["last_sequence_processed"],
                "updated_at": state["updated_at"],
                "last_error_at": state["last_error_at"],
            }

    def list_jobs(
        self,
        printer_name: Optional[str] = None,
        statuses: Optional[Iterable[str]] = None,
        limit: Optional[int] = None,
    ) -> List[JobRecord]:
        """Fetch jobs filtered by printer/status."""
        conditions = []
        params: List[Any] = []
        if printer_name:
            conditions.append("printer_name = ?")
            params.append(printer_name)
        if statuses:
            placeholders = ",".join("?" for _ in statuses)
            conditions.append(f"status IN ({placeholders})")
            params.extend(statuses)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        limit_clause = f"LIMIT {int(limit)}" if limit else ""

        query = f"""
            SELECT * FROM print_jobs
            {where_clause}
            ORDER BY created_at DESC
            {limit_clause}
        """

        with self._cursor() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()

        return [self._row_to_record(row) for row in rows]

    def count_pending(self, printer_name: str) -> int:
        """Count queued jobs for a printer."""
        with self._cursor() as conn:
            row = conn.execute(
                """
                SELECT COUNT(1) AS cnt
                FROM print_jobs
                WHERE printer_name = ?
                  AND status IN ('queued', 'retry_waiting')
                """,
                (printer_name,),
            ).fetchone()
        return int(row["cnt"]) if row else 0

    def detect_sequence_gaps(self, printer_name: str) -> List[Dict[str, Any]]:
        """Detect sequence gaps between queued/completed jobs."""
        with self._cursor() as conn:
            rows = conn.execute(
                """
                SELECT sequence_number, status, id
                FROM print_jobs
                WHERE printer_name = ?
                ORDER BY sequence_number ASC
                """,
                (printer_name,),
            ).fetchall()

        expected = 1
        gaps: List[Dict[str, Any]] = []
        for row in rows:
            seq = row["sequence_number"]
            if seq > expected:
                gaps.append(
                    {
                        "expected": expected,
                        "found": seq,
                        "missing_count": seq - expected,
                    }
                )
            expected = seq + 1

        return gaps

    def requeue_job(self, job_id: str, *, reset_attempts: bool = False) -> Optional[JobRecord]:
        """Requeue a job (for manual recovery)."""
        now_iso = _iso(_utcnow())
        with self._cursor() as conn:
            row = conn.execute(
                "SELECT * FROM print_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
            if not row:
                logger.warning("Attempted to requeue unknown job %s", job_id)
                return None

            printer_name = row["printer_name"]

            conn.execute(
                """
                UPDATE print_jobs
                SET status = 'queued',
                    available_at = ?,
                    updated_at = ?,
                    error_message = NULL,
                    attempts = CASE WHEN ? THEN 0 ELSE attempts END,
                    verification_status = 'pending',
                    verification_message = NULL,
                    completed_at = NULL
                WHERE id = ?
                """,
                (now_iso, now_iso, 1 if reset_attempts else 0, job_id),
            )

            self._insert_event(conn, job_id, printer_name, "requeued", "manual recovery")

            conn.execute(
                """
                UPDATE printer_state
                SET paused = 0,
                    pause_reason = NULL,
                    updated_at = ?
                WHERE printer_name = ?
                """,
                (now_iso, printer_name),
            )

            row = conn.execute("SELECT * FROM print_jobs WHERE id = ?", (job_id,)).fetchone()

        return self._row_to_record(row) if row else None

    def get_unprinted_jobs(self, printer_name: Optional[str] = None) -> List[JobRecord]:
        """Return jobs that are not completed."""
        statuses = ("queued", "retry_waiting", "processing", "printing", "failed")
        return self.list_jobs(printer_name=printer_name, statuses=statuses)

    def resume_printer(self, printer_name: str) -> None:
        """Resume a paused printer queue."""
        now_iso = _iso(_utcnow())
        with self._cursor() as conn:
            conn.execute(
                """
                UPDATE printer_state
                SET paused = 0,
                    pause_reason = NULL,
                    updated_at = ?
                WHERE printer_name = ?
                """,
                (now_iso, printer_name),
            )


# Global instance
DEFAULT_DB_PATH = os.path.join("data", "print_jobs.db")
job_store = JobStore(DEFAULT_DB_PATH)


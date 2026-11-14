"""IOA SQLite database layer.

Persistent local state (local-first policy):

- contacts, campaigns, approval_records, scheduling_records, sending_attempts
- error_logs, app_configuration, execution_locks

All tables use UUID primary keys and explicit transactions.
SQLite is file-based on the user's Windows machine — no cloud database.
"""

from __future__ import annotations

import sqlite3
import threading
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, Iterable

from data.models import (
    Contact, Campaign, ApprovalRecord, SchedulingRecord, SendingAttempt,
    ErrorLog, AppConfiguration, ExecutionLock,
    ContactStatus, CampaignState, SendOutcome,
)


class Database:
    """Thread-safe SQLite wrapper for IOA local state."""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ #
    # Connection management
    # ------------------------------------------------------------------ #
    def _get_connection(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(str(self.db_path), timeout=30, isolation_level=None)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
            self._local.conn = conn
        return conn

    def close(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            try:
                conn.close()
            finally:
                self._local.conn = None

    @contextmanager
    def transaction(self):
        """Provide a transactional scope around a series of operations."""
        conn = self._get_connection()
        try:
            conn.execute("BEGIN")
            yield conn
            conn.execute("COMMIT")
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
            raise

    # ------------------------------------------------------------------ #
    # Schema
    # ------------------------------------------------------------------ #
    def initialize(self) -> None:
        """Create all tables if they do not exist."""
        # executescript implicitly commits any open transaction in SQLite,
        # so we run it directly on the connection (not inside BEGIN/COMMIT).
        conn = self._get_connection()
        conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS contacts (
                    id TEXT PRIMARY KEY,
                    excel_row_index INTEGER,
                    institute_name TEXT NOT NULL,
                    phone_original TEXT NOT NULL,
                    phone_normalized TEXT,
                    address TEXT DEFAULT '',
                    contact_status TEXT DEFAULT 'pending',
                    notes TEXT DEFAULT '',
                    last_sent_at TEXT,
                    failure_reason TEXT,
                    is_contacted INTEGER DEFAULT 0,
                    campaign_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS campaigns (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    template_content TEXT DEFAULT '',
                    state TEXT DEFAULT 'draft',
                    start_date TEXT,
                    start_time TEXT,
                    interval_seconds INTEGER DEFAULT 60,
                    max_messages_per_session INTEGER DEFAULT 50,
                    sending_start_hour INTEGER DEFAULT 9,
                    sending_end_hour INTEGER DEFAULT 17,
                    total_contacts INTEGER DEFAULT 0,
                    sent_count INTEGER DEFAULT 0,
                    failed_count INTEGER DEFAULT 0,
                    uncertain_count INTEGER DEFAULT 0,
                    skipped_count INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    paused_at TEXT,
                    completed_at TEXT
                );

                CREATE TABLE IF NOT EXISTS approval_records (
                    id TEXT PRIMARY KEY,
                    contact_id TEXT NOT NULL,
                    campaign_id TEXT NOT NULL,
                    message_hash TEXT NOT NULL,
                    message_preview TEXT DEFAULT '',
                    institute_name TEXT NOT NULL,
                    phone_number TEXT NOT NULL,
                    proposed_send_at TEXT,
                    expires_at TEXT,
                    status TEXT DEFAULT 'pending',
                    telegram_message_id INTEGER,
                    created_at TEXT NOT NULL,
                    executed_at TEXT,
                    FOREIGN KEY (contact_id) REFERENCES contacts(id),
                    FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
                );

                CREATE TABLE IF NOT EXISTS scheduling_records (
                    id TEXT PRIMARY KEY,
                    campaign_id TEXT NOT NULL,
                    contact_id TEXT NOT NULL,
                    scheduled_at TEXT,
                    status TEXT DEFAULT 'pending',
                    approval_id TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (campaign_id) REFERENCES campaigns(id),
                    FOREIGN KEY (contact_id) REFERENCES contacts(id),
                    FOREIGN KEY (approval_id) REFERENCES approval_records(id)
                );

                CREATE TABLE IF NOT EXISTS sending_attempts (
                    id TEXT PRIMARY KEY,
                    contact_id TEXT NOT NULL,
                    campaign_id TEXT NOT NULL,
                    approval_id TEXT,
                    phone_number TEXT NOT NULL,
                    institute_name TEXT NOT NULL,
                    outcome TEXT DEFAULT 'uncertain',
                    error_message TEXT,
                    sent_at TEXT,
                    verified_at TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (contact_id) REFERENCES contacts(id),
                    FOREIGN KEY (campaign_id) REFERENCES campaigns(id),
                    FOREIGN KEY (approval_id) REFERENCES approval_records(id)
                );

                CREATE TABLE IF NOT EXISTS error_logs (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    level TEXT DEFAULT 'ERROR',
                    source TEXT DEFAULT '',
                    message TEXT NOT NULL,
                    contact_id TEXT,
                    campaign_id TEXT,
                    recovery_action TEXT
                );

                CREATE TABLE IF NOT EXISTS app_configuration (
                    key TEXT PRIMARY KEY,
                    value TEXT DEFAULT '',
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS execution_locks (
                    id TEXT PRIMARY KEY,
                    lock_name TEXT NOT NULL UNIQUE,
                    acquired_at TEXT NOT NULL,
                    expires_at TEXT,
                    holder TEXT DEFAULT ''
                );

                CREATE INDEX IF NOT EXISTS idx_contacts_campaign ON contacts(campaign_id);
                CREATE INDEX IF NOT EXISTS idx_contacts_status ON contacts(contact_status);
                CREATE INDEX IF NOT EXISTS idx_approvals_campaign ON approval_records(campaign_id);
                CREATE INDEX IF NOT EXISTS idx_approvals_contact ON approval_records(contact_id);
                CREATE INDEX IF NOT EXISTS idx_scheduling_campaign ON scheduling_records(campaign_id);
                CREATE INDEX IF NOT EXISTS idx_attempts_campaign ON sending_attempts(campaign_id);
                CREATE INDEX IF NOT EXISTS idx_locks_name ON execution_locks(lock_name);
                """
            )

    # ------------------------------------------------------------------ #
    # Contacts
    # ------------------------------------------------------------------ #
    def upsert_contact(self, contact: Contact) -> str:
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO contacts (
                    id, excel_row_index, institute_name, phone_original,
                    phone_normalized, address, contact_status, notes,
                    last_sent_at, failure_reason, is_contacted, campaign_id,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    excel_row_index=excluded.excel_row_index,
                    institute_name=excluded.institute_name,
                    phone_original=excluded.phone_original,
                    phone_normalized=excluded.phone_normalized,
                    address=excluded.address,
                    contact_status=excluded.contact_status,
                    notes=excluded.notes,
                    last_sent_at=excluded.last_sent_at,
                    failure_reason=excluded.failure_reason,
                    is_contacted=excluded.is_contacted,
                    campaign_id=excluded.campaign_id,
                    updated_at=excluded.updated_at
                """,
                (
                    contact.id, contact.excel_row_index, contact.institute_name,
                    contact.phone_original, contact.phone_normalized,
                    contact.address, contact.contact_status, contact.notes,
                    contact.last_sent_at, contact.failure_reason,
                    int(contact.is_contacted), contact.campaign_id,
                    contact.created_at, contact.updated_at,
                ),
            )
        return contact.id

    def get_contact(self, contact_id: str) -> Optional[Contact]:
        with self.transaction() as conn:
            row = conn.execute(
                "SELECT * FROM contacts WHERE id = ?", (contact_id,)
            ).fetchone()
        return self._row_to_contact(row) if row else None

    def get_contact_by_phone(self, phone_normalized: str) -> Optional[Contact]:
        with self.transaction() as conn:
            row = conn.execute(
                "SELECT * FROM contacts WHERE phone_normalized = ?",
                (phone_normalized,),
            ).fetchone()
        return self._row_to_contact(row) if row else None

    def list_contacts(
        self,
        campaign_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[Contact]:
        sql = "SELECT * FROM contacts WHERE 1=1"
        params: list = []
        if campaign_id:
            sql += " AND campaign_id = ?"
            params.append(campaign_id)
        if status:
            sql += " AND contact_status = ?"
            params.append(status)
        sql += " ORDER BY institute_name"
        if limit:
            sql += " LIMIT ?"
            params.append(limit)
        with self.transaction() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_contact(r) for r in rows]

    def mark_contact_sent(self, contact_id: str, sent_at: str) -> None:
        with self.transaction() as conn:
            conn.execute(
                """
                UPDATE contacts
                SET contact_status = 'sent',
                    is_contacted = 1,
                    last_sent_at = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (sent_at, sent_at, contact_id),
            )

    def mark_contact_failed(
        self, contact_id: str, failure_reason: str
    ) -> None:
        with self.transaction() as conn:
            conn.execute(
                """
                UPDATE contacts
                SET contact_status = 'failed',
                    failure_reason = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (failure_reason, datetime_utcnow(), contact_id),
            )

    def mark_contact_uncertain(self, contact_id: str) -> None:
        with self.transaction() as conn:
            conn.execute(
                """
                UPDATE contacts
                SET contact_status = 'uncertain',
                    updated_at = ?
                WHERE id = ?
                """,
                (datetime_utcnow(), contact_id),
            )

    # ------------------------------------------------------------------ #
    # Campaigns
    # ------------------------------------------------------------------ #
    def create_campaign(self, campaign: Campaign) -> str:
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO campaigns (
                    id, name, template_content, state, start_date, start_time,
                    interval_seconds, max_messages_per_session,
                    sending_start_hour, sending_end_hour,
                    total_contacts, sent_count, failed_count,
                    uncertain_count, skipped_count,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    campaign.id, campaign.name, campaign.template_content,
                    campaign.state,
                    campaign.start_date, campaign.start_time,
                    campaign.interval_seconds, campaign.max_messages_per_session,
                    campaign.sending_start_hour, campaign.sending_end_hour,
                    campaign.total_contacts, campaign.sent_count,
                    campaign.failed_count, campaign.uncertain_count,
                    campaign.skipped_count,
                    campaign.created_at, campaign.updated_at,
                ),
            )
        return campaign.id

    def get_campaign(self, campaign_id: str) -> Optional[Campaign]:
        with self.transaction() as conn:
            row = conn.execute(
                "SELECT * FROM campaigns WHERE id = ?", (campaign_id,)
            ).fetchone()
        return self._row_to_campaign(row) if row else None

    def list_campaigns(self) -> list[Campaign]:
        with self.transaction() as conn:
            rows = conn.execute(
                "SELECT * FROM campaigns ORDER BY created_at DESC"
            ).fetchall()
        return [self._row_to_campaign(r) for r in rows]

    def update_campaign(self, campaign: Campaign) -> None:
        with self.transaction() as conn:
            conn.execute(
                """
                UPDATE campaigns SET
                    name=?, template_content=?, state=?, start_date=?, start_time=?,
                    interval_seconds=?, max_messages_per_session=?,
                    sending_start_hour=?, sending_end_hour=?,
                    total_contacts=?, sent_count=?, failed_count=?,
                    uncertain_count=?, skipped_count=?,
                    updated_at=?, paused_at=?, completed_at=?
                WHERE id=?
                """,
                (
                    campaign.name, campaign.template_content, campaign.state,
                    campaign.start_date,
                    campaign.start_time, campaign.interval_seconds,
                    campaign.max_messages_per_session,
                    campaign.sending_start_hour, campaign.sending_end_hour,
                    campaign.total_contacts, campaign.sent_count,
                    campaign.failed_count, campaign.uncertain_count,
                    campaign.skipped_count,
                    campaign.updated_at, campaign.paused_at,
                    campaign.completed_at, campaign.id,
                ),
            )

    def set_campaign_state(
        self, campaign_id: str, state: str, now: Optional[str] = None
    ) -> None:
        now = now or datetime_utcnow()
        extra = ""
        params: list = [state, now, campaign_id]
        if state == CampaignState.PAUSED:
            extra = ", paused_at = ?"
            params.insert(2, now)
        elif state == CampaignState.COMPLETED:
            extra = ", completed_at = ?"
            params.insert(2, now)
        with self.transaction() as conn:
            conn.execute(
                f"UPDATE campaigns SET state = ?, updated_at = ?{extra} WHERE id = ?",
                params,
            )

    # ------------------------------------------------------------------ #
    # Approval records
    # ------------------------------------------------------------------ #
    def create_approval(self, approval: ApprovalRecord) -> str:
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO approval_records (
                    id, contact_id, campaign_id, message_hash,
                    message_preview, institute_name, phone_number,
                    proposed_send_at, expires_at, status,
                    telegram_message_id, created_at, executed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    approval.id, approval.contact_id, approval.campaign_id,
                    approval.message_hash, approval.message_preview,
                    approval.institute_name, approval.phone_number,
                    approval.proposed_send_at, approval.expires_at,
                    approval.status, approval.telegram_message_id,
                    approval.created_at, approval.executed_at,
                ),
            )
        return approval.id

    def get_approval(self, approval_id: str) -> Optional[ApprovalRecord]:
        with self.transaction() as conn:
            row = conn.execute(
                "SELECT * FROM approval_records WHERE id = ?", (approval_id,)
            ).fetchone()
        return self._row_to_approval(row) if row else None

    def get_approval_by_contact_and_campaign(
        self, contact_id: str, campaign_id: str
    ) -> Optional[ApprovalRecord]:
        with self.transaction() as conn:
            row = conn.execute(
                """
                SELECT * FROM approval_records
                WHERE contact_id = ? AND campaign_id = ?
                ORDER BY created_at DESC LIMIT 1
                """,
                (contact_id, campaign_id),
            ).fetchone()
        return self._row_to_approval(row) if row else None

    def list_pending_approvals(self) -> list[ApprovalRecord]:
        with self.transaction() as conn:
            rows = conn.execute(
                """
                SELECT * FROM approval_records
                WHERE status = 'pending'
                ORDER BY created_at ASC
                """
            ).fetchall()
        return [self._row_to_approval(r) for r in rows]

    def list_expired_pending_approvals(self) -> list[ApprovalRecord]:
        """Return pending approvals whose expires_at is in the past."""
        now = datetime_utcnow()
        with self.transaction() as conn:
            rows = conn.execute(
                """
                SELECT * FROM approval_records
                WHERE status = 'pending' AND expires_at IS NOT NULL
                  AND expires_at < ?
                """,
                (now,),
            ).fetchall()
        return [self._row_to_approval(r) for r in rows]

    def update_approval_status(
        self, approval_id: str, status: str, executed_at: Optional[str] = None
    ) -> None:
        with self.transaction() as conn:
            if executed_at:
                conn.execute(
                    """
                    UPDATE approval_records
                    SET status = ?, executed_at = ?
                    WHERE id = ?
                    """,
                    (status, executed_at, approval_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE approval_records
                    SET status = ?
                    WHERE id = ?
                    """,
                    (status, approval_id),
                )

    # ------------------------------------------------------------------ #
    # Scheduling records
    # ------------------------------------------------------------------ #
    def create_scheduling_record(self, record: SchedulingRecord) -> str:
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO scheduling_records (
                    id, campaign_id, contact_id, scheduled_at,
                    status, approval_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id, record.campaign_id, record.contact_id,
                    record.scheduled_at, record.status,
                    record.approval_id, record.created_at,
                ),
            )
        return record.id

    def list_due_scheduling_records(
        self, now_iso: str, limit: int = 100
    ) -> list[SchedulingRecord]:
        """Records scheduled at or before now that are still pending."""
        with self.transaction() as conn:
            rows = conn.execute(
                """
                SELECT * FROM scheduling_records
                WHERE status = 'pending' AND scheduled_at IS NOT NULL
                  AND scheduled_at <= ?
                ORDER BY scheduled_at ASC
                LIMIT ?
                """,
                (now_iso, limit),
            ).fetchall()
        return [self._row_to_scheduling(r) for r in rows]

    def update_scheduling_status(
        self, record_id: str, status: str
    ) -> None:
        with self.transaction() as conn:
            conn.execute(
                "UPDATE scheduling_records SET status = ? WHERE id = ?",
                (status, record_id),
            )

    # ------------------------------------------------------------------ #
    # Sending attempts
    # ------------------------------------------------------------------ #
    def create_sending_attempt(self, attempt: SendingAttempt) -> str:
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO sending_attempts (
                    id, contact_id, campaign_id, approval_id,
                    phone_number, institute_name, outcome,
                    error_message, sent_at, verified_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    attempt.id, attempt.contact_id, attempt.campaign_id,
                    attempt.approval_id, attempt.phone_number,
                    attempt.institute_name, attempt.outcome,
                    attempt.error_message, attempt.sent_at,
                    attempt.verified_at, attempt.created_at,
                ),
            )
        return attempt.id

    def list_attempts_for_contact(
        self, contact_id: str, limit: int = 10
    ) -> list[SendingAttempt]:
        with self.transaction() as conn:
            rows = conn.execute(
                """
                SELECT * FROM sending_attempts
                WHERE contact_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (contact_id, limit),
            ).fetchall()
        return [self._row_to_attempt(r) for r in rows]

    # ------------------------------------------------------------------ #
    # Error logs
    # ------------------------------------------------------------------ #
    def log_error(
        self,
        message: str,
        source: str = "",
        level: str = "ERROR",
        contact_id: Optional[str] = None,
        campaign_id: Optional[str] = None,
        recovery_action: Optional[str] = None,
    ) -> str:
        err = ErrorLog(
            source=source,
            level=level,
            message=message,
            contact_id=contact_id,
            campaign_id=campaign_id,
            recovery_action=recovery_action,
        )
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO error_logs (
                    id, timestamp, level, source, message,
                    contact_id, campaign_id, recovery_action
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    err.id, err.timestamp, err.level, err.source,
                    err.message, err.contact_id, err.campaign_id,
                    err.recovery_action,
                ),
            )
        return err.id

    def list_error_logs(self, limit: int = 200) -> list[ErrorLog]:
        with self.transaction() as conn:
            rows = conn.execute(
                "SELECT * FROM error_logs ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_error(r) for r in rows]

    # ------------------------------------------------------------------ #
    # App configuration (key/value)
    # ------------------------------------------------------------------ #
    def set_config(self, key: str, value: str) -> None:
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO app_configuration (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (key, value, datetime_utcnow()),
            )

    def get_config(self, key: str, default: Optional[str] = None) -> Optional[str]:
        with self.transaction() as conn:
            row = conn.execute(
                "SELECT value FROM app_configuration WHERE key = ?", (key,)
            ).fetchone()
        return row["value"] if row else default

    # ------------------------------------------------------------------ #
    # Execution locks (prevent overlapping scheduler jobs)
    # ------------------------------------------------------------------ #
    def acquire_lock(
        self, lock_name: str, holder: str, ttl_seconds: int = 300
    ) -> bool:
        from datetime import datetime, timedelta

        now = datetime.utcnow()
        expires = (now + timedelta(seconds=ttl_seconds)).isoformat(timespec="seconds")
        try:
            with self.transaction() as conn:
                conn.execute(
                    """
                    INSERT INTO execution_locks (id, lock_name, acquired_at, expires_at, holder)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()), lock_name, now.isoformat(timespec="seconds"),
                        expires, holder,
                    ),
                )
            return True
        except sqlite3.IntegrityError:
            # Lock exists — check if it is expired
            with self.transaction() as conn:
                row = conn.execute(
                    "SELECT * FROM execution_locks WHERE lock_name = ?",
                    (lock_name,),
                ).fetchone()
                if row and ExecutionLock(
                    id=row["id"],
                    lock_name=row["lock_name"],
                    acquired_at=row["acquired_at"],
                    expires_at=row["expires_at"],
                    holder=row["holder"],
                ).is_expired:
                    conn.execute(
                        "DELETE FROM execution_locks WHERE lock_name = ?",
                        (lock_name,),
                    )
                    conn.execute(
                        """
                        INSERT INTO execution_locks (id, lock_name, acquired_at, expires_at, holder)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            str(uuid.uuid4()), lock_name,
                            now.isoformat(timespec="seconds"), expires, holder,
                        ),
                    )
                    return True
            return False

    def release_lock(self, lock_name: str) -> None:
        with self.transaction() as conn:
            conn.execute(
                "DELETE FROM execution_locks WHERE lock_name = ?", (lock_name,)
            )

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _row_to_contact(row: sqlite3.Row) -> Contact:
        return Contact(
            id=row["id"],
            excel_row_index=row["excel_row_index"],
            institute_name=row["institute_name"],
            phone_original=row["phone_original"],
            phone_normalized=row["phone_normalized"],
            address=row["address"] or "",
            contact_status=row["contact_status"],
            notes=row["notes"] or "",
            last_sent_at=row["last_sent_at"],
            failure_reason=row["failure_reason"],
            is_contacted=bool(row["is_contacted"]),
            campaign_id=row["campaign_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _row_to_campaign(row: sqlite3.Row) -> Campaign:
        return Campaign(
            id=row["id"],
            name=row["name"],
            template_content=row["template_content"],
            state=row["state"],
            start_date=row["start_date"],
            start_time=row["start_time"],
            interval_seconds=row["interval_seconds"],
            max_messages_per_session=row["max_messages_per_session"],
            sending_start_hour=row["sending_start_hour"],
            sending_end_hour=row["sending_end_hour"],
            total_contacts=row["total_contacts"],
            sent_count=row["sent_count"],
            failed_count=row["failed_count"],
            uncertain_count=row["uncertain_count"],
            skipped_count=row["skipped_count"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            paused_at=row["paused_at"],
            completed_at=row["completed_at"],
        )

    @staticmethod
    def _row_to_approval(row: sqlite3.Row) -> ApprovalRecord:
        return ApprovalRecord(
            id=row["id"],
            contact_id=row["contact_id"],
            campaign_id=row["campaign_id"],
            message_hash=row["message_hash"],
            message_preview=row["message_preview"],
            institute_name=row["institute_name"],
            phone_number=row["phone_number"],
            proposed_send_at=row["proposed_send_at"],
            expires_at=row["expires_at"],
            status=row["status"],
            telegram_message_id=row["telegram_message_id"],
            created_at=row["created_at"],
            executed_at=row["executed_at"],
        )

    @staticmethod
    def _row_to_scheduling(row: sqlite3.Row) -> SchedulingRecord:
        return SchedulingRecord(
            id=row["id"],
            campaign_id=row["campaign_id"],
            contact_id=row["contact_id"],
            scheduled_at=row["scheduled_at"],
            status=row["status"],
            approval_id=row["approval_id"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _row_to_attempt(row: sqlite3.Row) -> SendingAttempt:
        return SendingAttempt(
            id=row["id"],
            contact_id=row["contact_id"],
            campaign_id=row["campaign_id"],
            approval_id=row["approval_id"],
            phone_number=row["phone_number"],
            institute_name=row["institute_name"],
            outcome=row["outcome"],
            error_message=row["error_message"],
            sent_at=row["sent_at"],
            verified_at=row["verified_at"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _row_to_error(row: sqlite3.Row) -> ErrorLog:
        return ErrorLog(
            id=row["id"],
            timestamp=row["timestamp"],
            level=row["level"],
            source=row["source"],
            message=row["message"],
            contact_id=row["contact_id"],
            campaign_id=row["campaign_id"],
            recovery_action=row["recovery_action"],
        )


def datetime_utcnow() -> str:
    from datetime import datetime

    return datetime.utcnow().isoformat(timespec="seconds")

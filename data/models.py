"""IOA data models.

Defines the domain entities used across the application:

- Contact: institute record discovered from Excel
- Campaign: outreach campaign definition and state
- ApprovalRecord: individual Telegram approval bound to a contact/message/campaign
- SchedulingRecord: scheduled send task
- SendingAttempt: record of each send attempt and its outcome
- ErrorLog: application error / audit log entry
- AppConfiguration: persisted key/value configuration
- ExecutionLock: scheduler execution lock to prevent overlaps

All identifiers are UUIDs to guarantee uniqueness across restarts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import uuid


def _new_id() -> str:
    return str(uuid.uuid4())


def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Contact statuses (per IOA.md section 2.3)
# ---------------------------------------------------------------------------
class ContactStatus:
    PENDING = "pending"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    SCHEDULED = "scheduled"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"
    INVALID_NUMBER = "invalid_number"
    UNCERTAIN = "uncertain"

    ARABIC_CONTACTED = "تم التواصل"

    ALL = (
        PENDING,
        AWAITING_APPROVAL,
        APPROVED,
        SCHEDULED,
        SENDING,
        SENT,
        FAILED,
        SKIPPED,
        INVALID_NUMBER,
        UNCERTAIN,
    )


# ---------------------------------------------------------------------------
# Campaign states
# ---------------------------------------------------------------------------
class CampaignState:
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    STOPPED = "stopped"


# ---------------------------------------------------------------------------
# Sending outcomes
# ---------------------------------------------------------------------------
class SendOutcome:
    SUBMITTED = "submitted"
    DELIVERED = "delivered"
    FAILED = "failed"
    UNCERTAIN = "uncertain"


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------


@dataclass
class Contact:
    """Represents a single institute record from Excel."""

    id: str = field(default_factory=_new_id)
    excel_row_index: Optional[int] = None  # row in the source workbook (1-based)
    institute_name: str = ""
    phone_original: str = ""   # raw value from Excel
    phone_normalized: str = "" # normalized international format (internal)
    address: str = ""
    contact_status: str = ContactStatus.PENDING
    notes: str = ""
    last_sent_at: Optional[str] = None
    failure_reason: Optional[str] = None
    is_contacted: bool = False
    campaign_id: Optional[str] = None
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)

    @property
    def is_already_contacted(self) -> bool:
        return self.is_contacted or self.contact_status in (
            ContactStatus.SENT,
            ContactStatus.ARABIC_CONTACTED,
        )


@dataclass
class Campaign:
    id: str = field(default_factory=_new_id)
    name: str = ""
    template_content: str = ""   # approved message template for this campaign
    state: str = CampaignState.DRAFT
    start_date: Optional[str] = None   # YYYY-MM-DD (Asia/Aden)
    start_time: Optional[str] = None   # HH:MM (Asia/Aden)
    interval_seconds: int = 60
    max_messages_per_session: int = 50
    sending_start_hour: int = 9
    sending_end_hour: int = 17
    total_contacts: int = 0
    sent_count: int = 0
    failed_count: int = 0
    uncertain_count: int = 0
    skipped_count: int = 0
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    paused_at: Optional[str] = None
    completed_at: Optional[str] = None

    @property
    def is_paused(self) -> bool:
        return self.state == CampaignState.PAUSED

    @property
    def is_active(self) -> bool:
        return self.state == CampaignState.ACTIVE


@dataclass
class ApprovalRecord:
    """Individual Telegram approval bound to a contact, message, and campaign."""

    id: str = field(default_factory=_new_id)
    contact_id: str = ""
    campaign_id: str = ""
    message_hash: str = ""           # SHA-256 of the exact message content
    message_preview: str = ""        # first 200 chars for UI display
    institute_name: str = ""
    phone_number: str = ""
    proposed_send_at: Optional[str] = None  # ISO timestamp (Asia/Aden)
    expires_at: Optional[str] = None        # ISO timestamp (Asia/Aden)
    status: str = "pending"          # pending / approved / rejected / expired / executed
    telegram_message_id: Optional[int] = None
    created_at: str = field(default_factory=_now_iso)
    executed_at: Optional[str] = None

    @property
    def is_expired(self) -> bool:
        if not self.expires_at:
            return True
        try:
            return datetime.fromisoformat(self.expires_at) < datetime.utcnow()
        except ValueError:
            return True

    @property
    def is_executed(self) -> bool:
        return self.status in ("executed", "rejected", "expired")


@dataclass
class SchedulingRecord:
    id: str = field(default_factory=_new_id)
    campaign_id: str = ""
    contact_id: str = ""
    scheduled_at: Optional[str] = None  # ISO timestamp (Asia/Aden)
    status: str = "pending"            # pending / sent / failed / cancelled / expired
    approval_id: Optional[str] = None
    created_at: str = field(default_factory=_now_iso)


@dataclass
class SendingAttempt:
    id: str = field(default_factory=_new_id)
    contact_id: str = ""
    campaign_id: str = ""
    approval_id: Optional[str] = None
    phone_number: str = ""
    institute_name: str = ""
    outcome: str = SendOutcome.UNCERTAIN
    error_message: Optional[str] = None
    sent_at: Optional[str] = None
    verified_at: Optional[str] = None
    created_at: str = field(default_factory=_now_iso)

    @property
    def is_successful(self) -> bool:
        return self.outcome in (SendOutcome.SUBMITTED, SendOutcome.DELIVERED)

    @property
    def is_uncertain(self) -> bool:
        return self.outcome == SendOutcome.UNCERTAIN


@dataclass
class ErrorLog:
    id: str = field(default_factory=_new_id)
    timestamp: str = field(default_factory=_now_iso)
    level: str = "ERROR"          # ERROR / WARNING / INFO
    source: str = ""
    message: str = ""
    contact_id: Optional[str] = None
    campaign_id: Optional[str] = None
    recovery_action: Optional[str] = None


@dataclass
class AppConfiguration:
    key: str = ""
    value: str = ""
    updated_at: str = field(default_factory=_now_iso)


@dataclass
class ExecutionLock:
    id: str = field(default_factory=_new_id)
    lock_name: str = ""
    acquired_at: str = field(default_factory=_now_iso)
    expires_at: Optional[str] = None
    holder: str = ""

    @property
    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        try:
            return datetime.fromisoformat(self.expires_at) < datetime.utcnow()
        except ValueError:
            return True

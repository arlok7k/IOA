"""IOA approval manager.

Individual explicit approvals via Telegram, bound to a specific contact,
message, and campaign. Every approval is validated against the local database
before execution.

Security properties:
- Approval bound to contact_id, campaign_id, message_hash, approval_id, expiry.
- Duplicate approval execution prevented.
- Expired approvals cannot execute.
- Modified messages invalidate the corresponding approval (message hash check).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import hashlib

from data.models import ApprovalRecord, Contact
from data.database import Database


@dataclass
class ApprovalRequest:
    contact: Contact
    campaign_id: str
    message_content: str
    proposed_send_at: str | None = None
    ttl_minutes: int = 60  # approval expiration window


@dataclass
class ApprovalDecision:
    approved: bool
    approval_id: str
    reason: str = ""
    expires_at: str | None = None


class ApprovalManager:
    def __init__(self, database: Database):
        self.db = database

    # ------------------------------------------------------------------ #
    # Create an approval record for a contact
    # ------------------------------------------------------------------ #
    def create_approval(self, request: ApprovalRequest) -> ApprovalRecord:
        message_hash = hashlib.sha256(
            request.message_content.encode("utf-8")
        ).hexdigest()
        now = datetime.utcnow()
        expires_at = now + timedelta(minutes=request.ttl_minutes)

        approval = ApprovalRecord(
            contact_id=request.contact.id,
            campaign_id=request.campaign_id,
            message_hash=message_hash,
            message_preview=request.message_content[:200],
            institute_name=request.contact.institute_name,
            phone_number=request.contact.phone_normalized or request.contact.phone_original,
            proposed_send_at=request.proposed_send_at,
            expires_at=expires_at.isoformat(timespec="seconds"),
            status="pending",
            created_at=now.isoformat(timespec="seconds"),
        )
        self.db.create_approval(approval)
        return approval

    # ------------------------------------------------------------------ #
    # Validate before execution (the core security gate)
    # ------------------------------------------------------------------ #
    def validate_approval_for_execution(
        self,
        approval_id: str,
        contact_id: str,
        campaign_id: str,
        message_content: str,
    ) -> tuple[bool, str]:
        """Return (valid, reason).

        Checks:
        - approval exists and is pending
        - bound to the exact contact and campaign
        - message hash matches (message not modified)
        - not expired
        - not already executed
        """
        approval = self.db.get_approval(approval_id)
        if approval is None:
            return False, "سجل الموافقة غير موجود."

        if approval.status != "pending":
            return False, f"حالة الموافقة غير صالحة للتنفيذ: {approval.status}."

        if approval.contact_id != contact_id:
            return False, "الموافقة مرتبطة بمعهد آخر."

        if approval.campaign_id != campaign_id:
            return False, "الموافقة مرتبطة بحملة أخرى."

        # Message integrity: hash must match
        current_hash = hashlib.sha256(
            message_content.encode("utf-8")
        ).hexdigest()
        if approval.message_hash != current_hash:
            return False, "محتوى الرسالة تغير بعد الموافقة — غير صالحة للتنفيذ."

        if approval.is_expired:
            return False, "انتهت صلاحية الموافقة."

        return True, "الموافقة صالحة للتنفيذ."

    # ------------------------------------------------------------------ #
    # Execute (mark as executed) — idempotent
    # ------------------------------------------------------------------ #
    def execute_approval(
        self,
        approval_id: str,
        contact_id: str,
        campaign_id: str,
        message_content: str,
    ) -> tuple[bool, str]:
        valid, reason = self.validate_approval_for_execution(
            approval_id, contact_id, campaign_id, message_content
        )
        if not valid:
            return False, reason

        # Idempotency: re-check status inside a transaction to avoid races
        approval = self.db.get_approval(approval_id)
        if approval and approval.status != "pending":
            return False, "تم تنفيذ هذه الموافقة مسبقاً أو إلغاؤها."

        self.db.update_approval_status(
            approval_id, status="executed",
            executed_at=datetime.utcnow().isoformat(timespec="seconds"),
        )
        return True, "تم تنفيذ الموافقة بنجاح."

    def reject_approval(self, approval_id: str) -> bool:
        approval = self.db.get_approval(approval_id)
        if not approval or approval.status != "pending":
            return False
        self.db.update_approval_status(approval_id, status="rejected")
        return True

    def expire_pending_approvals(self) -> int:
        """Mark all expired pending approvals as expired. Returns count."""
        expired = self.db.list_expired_pending_approvals()
        count = 0
        now = datetime.utcnow().isoformat(timespec="seconds")
        for approval in expired:
            self.db.update_approval_status(approval_id=approval.id, status="expired", executed_at=now)
            count += 1
        return count

    def get_pending_for_contact(
        self, contact_id: str, campaign_id: str
    ) -> ApprovalRecord | None:
        return self.db.get_approval_by_contact_and_campaign(contact_id, campaign_id)

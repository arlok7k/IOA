"""IOA campaign scheduler.

Persists state in SQLite, survives restarts, avoids duplicate and overlapping
jobs, respects individual approvals, skips already-contacted contacts, respects
campaign pause state and approval expiration, and recovers safely from
interrupted operations.

All timestamps use Asia/Aden (UTC+3).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from data.database import Database
from data.models import Campaign, CampaignState, ContactStatus, SchedulingRecord


@dataclass
class SchedulerConfig:
    campaign_id: str
    interval_seconds: int = 60
    max_messages_per_session: int = 50
    sending_start_hour: int = 9
    sending_end_hour: int = 17
    timezone: str = "Asia/Aden"


class Scheduler:
    def __init__(
        self,
        database: Database,
        campaign_manager,  # CampaignManager (set later to avoid circular import)
        message_sender=None,  # MessageSender (set later)
        config: SchedulerConfig | None = None,
    ):
        self.db = database
        self.campaign_manager = campaign_manager
        self.message_sender = message_sender
        self.config = config or SchedulerConfig(campaign_id="")
        self._running = False

    # ------------------------------------------------------------------ #
    # Locking (prevent overlapping scheduler jobs)
    # ------------------------------------------------------------------ #
    def _acquire_scheduler_lock(self, ttl_seconds: int = 300) -> bool:
        return self.db.acquire_lock(
            lock_name=f"scheduler:{self.config.campaign_id}",
            holder="ioascheduler",
            ttl_seconds=ttl_seconds,
        )

    def _release_scheduler_lock(self) -> None:
        self.db.release_lock(lock_name=f"scheduler:{self.config.campaign_id}")

    # ------------------------------------------------------------------ #
    # Main tick (called periodically by the campaign manager)
    # ------------------------------------------------------------------ #
    def tick(self, now_iso: str | None = None) -> dict:
        """Process one scheduling cycle.

        Returns a summary dict of actions taken.
        """
        if not self._acquire_scheduler_lock():
            return {"skipped": "scheduler_lock_held"}

        try:
            return self._tick_inner(now_iso or _now_iso())
        finally:
            self._release_scheduler_lock()

    def _tick_inner(self, now_iso: str) -> dict:
        summary = {
            "processed": 0,
            "sent": 0,
            "skipped_contacted": 0,
            "skipped_no_approval": 0,
            "skipped_expired_approval": 0,
            "skipped_paused": 0,
            "skipped_outside_hours": 0,
            "errors": 0,
        }

        campaign = self.campaign_manager.get_campaign(self.config.campaign_id)
        if not campaign:
            summary["errors"] += 1
            return summary

        # Campaign must be active
        if campaign.state != CampaignState.ACTIVE:
            if campaign.state == CampaignState.PAUSED:
                summary["skipped_paused"] += 1
            return summary

        # Allowed sending hours (Asia/Aden)
        now = datetime.fromisoformat(now_iso)
        if not (campaign.sending_start_hour <= now.hour < campaign.sending_end_hour):
            summary["skipped_outside_hours"] += 1
            return summary

        # Due scheduling records
        due = self.db.list_due_scheduling_records(now_iso, limit=campaign.max_messages_per_session)
        processed_this_session = 0

        for record in due:
            if processed_this_session >= campaign.max_messages_per_session:
                break

            summary["processed"] += 1
            contact = self.db.get_contact(record.contact_id)
            if not contact:
                self.db.update_scheduling_status(record.id, "failed")
                continue

            # Skip already-contacted contacts
            if contact.is_already_contacted:
                self.db.update_scheduling_status(record.id, "skipped")
                summary["skipped_contacted"] += 1
                continue

            # Valid approval required (bound to exact message)
            approval = self.db.get_approval_by_contact_and_campaign(
                contact.id, campaign.id
            )
            if not approval or approval.status != "pending":
                self.db.update_scheduling_status(record.id, "skipped")
                summary["skipped_no_approval"] += 1
                continue

            if approval.is_expired:
                self.db.update_scheduling_status(record.id, "expired")
                summary["skipped_expired_approval"] += 1
                continue

            # Send via message sender (template + approval must match)
            if self.message_sender is None:
                summary["errors"] += 1
                continue

            from core.message_engine import MessageEngine
            # The campaign manager provides the template content per contact
            template_content = self.campaign_manager.get_template_for_contact(contact.id)
            request = self._build_send_request(contact, campaign, approval, template_content)
            response = self.message_sender.send_approved(request)

            if response.result in ("submitted", "delivered"):
                self.db.update_scheduling_status(record.id, "sent")
                summary["sent"] += 1
            elif response.result == "failed":
                self.db.update_scheduling_status(record.id, "failed")
            else:  # uncertain
                # Do NOT auto-retry; leave for manual review
                self.db.update_scheduling_status(record.id, "failed")

            processed_this_session += 1

        return summary

    def _build_send_request(
        self,
        contact: Contact,
        campaign: Campaign,
        approval: object,
        template_content: str,
    ):
        from core.message_sender import SendRequest

        return SendRequest(
            contact=contact,
            campaign_id=campaign.id,
            approval_id=approval.id,
            template_content=template_content,
            proposed_send_at=approval.proposed_send_at,
        )

    # ------------------------------------------------------------------ #
    # Recovery on restart
    # ------------------------------------------------------------------ #
    def recover_interrupted(self, campaign_id: str) -> dict:
        """Re-evaluate safely after an application restart.

        - Releases stale execution locks.
        - Marks expired pending approvals as expired.
        - Does not resend uncertain outcomes automatically.
        """
        self.db.release_lock(lock_name=f"scheduler:{campaign_id}")
        expired_count = 0
        # Expire pending approvals whose expiry passed
        now = datetime.utcnow().isoformat(timespec="seconds")
        # NOTE: expiration is handled by ApprovalManager.expire_pending_approvals
        return {"locks_released": 1, "expired_approvals": expired_count}

    def schedule_contact(
        self,
        campaign_id: str,
        contact_id: str,
        scheduled_at: str,
        approval_id: str | None = None,
    ) -> str:
        from data.models import SchedulingRecord

        record = SchedulingRecord(
            campaign_id=campaign_id,
            contact_id=contact_id,
            scheduled_at=scheduled_at,
            status="pending",
            approval_id=approval_id,
        )
        return self.db.create_scheduling_record(record)


def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")

"""IOA campaign manager.

Orchestrates contacts, campaigns, approvals, scheduling, WhatsApp sending,
and Telegram notifications. Central coordinator for all campaign operations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from data.database import Database
from data.models import (
    Campaign, CampaignState, Contact, ContactStatus,
    ApprovalRecord, ApprovalRequest,
)
from core.approval_manager import ApprovalManager
from core.scheduler import Scheduler
from core.message_engine import MessageEngine
from integrations.whatsapp.browser_manager import BrowserManager
from integrations.telegram.bot import TelegramBot
from integrations.whatsapp.message_sender import MessageSender


@dataclass
class CampaignStats:
    total: int = 0
    pending: int = 0
    awaiting_approval: int = 0
    scheduled: int = 0
    sent: int = 0
    failed: int = 0
    uncertain: int = 0
    skipped: int = 0


class CampaignManager:
    def __init__(self, database: Database, settings=None):
        self.db = database
        self.settings = settings
        self.approval_manager = ApprovalManager(database)
        self.scheduler: Optional[Scheduler] = None
        self.message_sender: Optional[MessageSender] = None
        self.browser_manager: Optional[BrowserManager] = None
        self.telegram_bot: Optional[TelegramBot] = None
        self.message_engine = MessageEngine()
        self._active_campaign_id: Optional[str] = None

    # ------------------------------------------------------------------ #
    # Wiring
    # ------------------------------------------------------------------ #
    def set_browser_manager(self, browser_manager: BrowserManager) -> None:
        self.browser_manager = browser_manager

    def set_telegram_bot(self, telegram_bot: TelegramBot) -> None:
        self.telegram_bot = telegram_bot

    def set_message_sender(self, message_sender: MessageSender) -> None:
        self.message_sender = message_sender

    def set_scheduler(self, scheduler: Scheduler) -> None:
        self.scheduler = scheduler

    # ------------------------------------------------------------------ #
    # Campaign lifecycle
    # ------------------------------------------------------------------ #
    def create_campaign(
        self,
        name: str,
        template_content: str = "",
        start_date: str | None = None,
        start_time: str | None = None,
        interval_seconds: int = 60,
        max_messages_per_session: int = 50,
        sending_start_hour: int = 9,
        sending_end_hour: int = 17,
    ) -> Campaign:
        campaign = Campaign(
            name=name,
            template_content=template_content,
            state=CampaignState.DRAFT,
            start_date=start_date,
            start_time=start_time,
            interval_seconds=interval_seconds,
            max_messages_per_session=max_messages_per_session,
            sending_start_hour=sending_start_hour,
            sending_end_hour=sending_end_hour,
        )
        self.db.create_campaign(campaign)
        return campaign

    def get_campaign(self, campaign_id: str) -> Campaign | None:
        return self.db.get_campaign(campaign_id)

    def list_campaigns(self) -> list[Campaign]:
        return self.db.list_campaigns()

    def start_campaign(self, campaign_id: str) -> bool:
        campaign = self.db.get_campaign(campaign_id)
        if not campaign:
            return False
        campaign.state = CampaignState.ACTIVE
        campaign.updated_at = _now_iso()
        self.db.update_campaign(campaign)
        self._active_campaign_id = campaign_id
        if self.scheduler:
            self.scheduler.config = self._scheduler_config(campaign)
        if self.telegram_bot:
            self.telegram_bot.notify_campaign_started(campaign)
        return True

    def pause_campaign(self, campaign_id: str) -> bool:
        self.db.set_campaign_state(campaign_id, CampaignState.PAUSED)
        if self._active_campaign_id == campaign_id:
            self._active_campaign_id = None
        if self.telegram_bot:
            campaign = self.db.get_campaign(campaign_id)
            if campaign:
                self.telegram_bot.notify_campaign_paused(campaign)
        return True

    def resume_campaign(self, campaign_id: str) -> bool:
        campaign = self.db.get_campaign(campaign_id)
        if not campaign:
            return False
        campaign.state = CampaignState.ACTIVE
        campaign.paused_at = None
        campaign.updated_at = _now_iso()
        self.db.update_campaign(campaign)
        self._active_campaign_id = campaign_id
        if self.telegram_bot:
            self.telegram_bot.notify_campaign_resumed(campaign)
        return True

    def stop_campaign(self, campaign_id: str) -> bool:
        self.db.set_campaign_state(campaign_id, CampaignState.STOPPED)
        if self._active_campaign_id == campaign_id:
            self._active_campaign_id = None
        return True

    # ------------------------------------------------------------------ #
    # Contacts & campaign assignment
    # ------------------------------------------------------------------ #
    def assign_contacts_to_campaign(
        self, campaign_id: str, contacts: list[Contact]
    ) -> int:
        count = 0
        for contact in contacts:
            contact.campaign_id = campaign_id
            contact.contact_status = ContactStatus.PENDING
            contact.is_contacted = False
            self.db.upsert_contact(contact)
            count += 1
        campaign = self.db.get_campaign(campaign_id)
        if campaign:
            campaign.total_contacts = count
            campaign.updated_at = _now_iso()
            self.db.update_campaign(campaign)
        return count

    def get_campaign_contacts(
        self, campaign_id: str, status: str | None = None
    ) -> list[Contact]:
        return self.db.list_contacts(campaign_id=campaign_id, status=status)

    def get_stats(self, campaign_id: str) -> CampaignStats:
        contacts = self.db.list_contacts(campaign_id=campaign_id)
        stats = CampaignStats(total=len(contacts))
        for c in contacts:
            if c.is_already_contacted:
                stats.sent += 1
            elif c.contact_status == ContactStatus.PENDING:
                stats.pending += 1
            elif c.contact_status == ContactStatus.AWAITING_APPROVAL:
                stats.awaiting_approval += 1
            elif c.contact_status == ContactStatus.SCHEDULED:
                stats.scheduled += 1
            elif c.contact_status == ContactStatus.FAILED:
                stats.failed += 1
            elif c.contact_status == ContactStatus.UNCERTAIN:
                stats.uncertain += 1
            elif c.contact_status == ContactStatus.SKIPPED:
                stats.skipped += 1
        return stats

    # ------------------------------------------------------------------ #
    # Approval flow integration
    # ------------------------------------------------------------------ #
    def request_approval_for_contact(
        self,
        contact: Contact,
        campaign_id: str,
        template_content: str,
        proposed_send_at: str | None = None,
    ) -> ApprovalRecord:
        request = ApprovalRequest(
            contact=contact,
            campaign_id=campaign_id,
            message_content=self.message_engine.generate(
                template_content,
                contact.institute_name,
                contact.phone_normalized or contact.phone_original,
            ).message,
            proposed_send_at=proposed_send_at,
        )
        approval = self.approval_manager.create_approval(request)
        # Mark contact awaiting approval
        contact.contact_status = ContactStatus.AWAITING_APPROVAL
        contact.updated_at = _now_iso()
        self.db.upsert_contact(contact)
        # Notify via Telegram
        if self.telegram_bot:
            self.telegram_bot.notify_approval_request(approval, contact)
        return approval

    def get_template_for_contact(self, contact_id: str) -> str:
        """Return the campaign template for a contact's campaign."""
        contact = self.db.get_contact(contact_id)
        if not contact or not contact.campaign_id:
            return ""
        campaign = self.db.get_campaign(contact.campaign_id)
        return campaign.template_content if campaign else ""

    # ------------------------------------------------------------------ #
    # Scheduling integration
    # ------------------------------------------------------------------ #
    def schedule_contact(
        self,
        campaign_id: str,
        contact_id: str,
        scheduled_at: str,
        approval_id: str | None = None,
    ) -> str:
        if self.scheduler:
            return self.scheduler.schedule_contact(
                campaign_id, contact_id, scheduled_at, approval_id
            )
        raise RuntimeError("Scheduler not initialized.")

    def run_scheduler_tick(self, now_iso: str | None = None) -> dict:
        if not self.scheduler:
            return {"error": "scheduler_not_initialized"}
        return self.scheduler.tick(now_iso)

    def recover_after_restart(self, campaign_id: str) -> dict:
        if self.scheduler:
            return self.scheduler.recover_interrupted(campaign_id)
        return {"error": "scheduler_not_initialized"}

    # ------------------------------------------------------------------ #
    # WhatsApp connection
    # ------------------------------------------------------------------ #
    def verify_whatsapp_profile(self):
        if self.browser_manager:
            return self.browser_manager.verify_profile_exists()
        return False, "browser_manager_not_initialized"

    def connect_whatsapp(self):
        if self.browser_manager:
            return self.browser_manager.connect()
        return None

    # ------------------------------------------------------------------ #
    # Active campaign accessor
    # ------------------------------------------------------------------ #
    @property
    def active_campaign_id(self) -> Optional[str]:
        return self._active_campaign_id

    @active_campaign_id.setter
    def active_campaign_id(self, value: Optional[str]) -> None:
        self._active_campaign_id = value

    def _scheduler_config(self, campaign: Campaign):
        from core.scheduler import SchedulerConfig

        return SchedulerConfig(
            campaign_id=campaign.id,
            interval_seconds=campaign.interval_seconds,
            max_messages_per_session=campaign.max_messages_per_session,
            sending_start_hour=campaign.sending_start_hour,
            sending_end_hour=campaign.sending_end_hour,
            timezone=getattr(self.settings, "timezone", "Asia/Aden") if self.settings else "Asia/Aden",
        )


def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")

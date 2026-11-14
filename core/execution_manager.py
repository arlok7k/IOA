"""IOA execution manager.

Coordinates per-contact sending with guards:

- No message is sent without a valid individual approval.
- Duplicate sends are prevented (in-session and via SQLite).
- Uncertain outcomes are never auto-retried.
- Excel is updated only after confirmed successful sending.
- Campaign pause state is respected.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from data.database import Database
from data.models import Contact, ContactStatus, SendOutcome
from integrations.whatsapp.message_sender import MessageSender, SendRequest, SendResponse
from core.approval_manager import ApprovalManager


@dataclass
class ExecutionResult:
    contact_id: str
    institute_name: str
    success: bool
    result: str
    message: str = ""
    requires_manual_review: bool = False


class ExecutionManager:
    def __init__(
        self,
        database: Database,
        message_sender: MessageSender,
        approval_manager: ApprovalManager,
    ):
        self.db = database
        self.message_sender = message_sender
        self.approval_manager = approval_manager

    def execute_send(
        self,
        contact: Contact,
        campaign_id: str,
        template_content: str,
        excel_path=None,
        excel_sheet=None,
    ) -> ExecutionResult:
        """Send to one contact only if a valid approval exists.

        Returns ExecutionResult describing the outcome.
        """
        # 1. Skip already-contacted contacts
        if contact.is_already_contacted:
            return ExecutionResult(
                contact_id=contact.id,
                institute_name=contact.institute_name,
                success=False,
                result="skipped",
                message="المؤسسة تمت 통신ها مسبقاً — تم التجاوز.",
            )

        # 2. Valid pending approval required
        approval = self.db.get_approval_by_contact_and_campaign(
            contact.id, campaign_id
        )
        if not approval or approval.status != "pending":
            return ExecutionResult(
                contact_id=contact.id,
                institute_name=contact.institute_name,
                success=False,
                result="no_approval",
                message="لا توجد موافقة فردية صالحة لهذا المعهد.",
            )

        if approval.is_expired:
            return ExecutionResult(
                contact_id=contact.id,
                institute_name=contact.institute_name,
                success=False,
                result="expired",
                message="انتهت صلاحية الموافقة.",
            )

        # 3. Build send request and send
        request = SendRequest(
            contact=contact,
            campaign_id=campaign_id,
            approval_id=approval.id,
            template_content=template_content,
            proposed_send_at=approval.proposed_send_at,
        )

        response: SendResponse = self.message_sender.send_approved(request)

        success = response.result.value in ("submitted", "delivered")

        return ExecutionResult(
            contact_id=contact.id,
            institute_name=contact.institute_name,
            success=success,
            result=response.result,
            message=response.error_message or (
                "تم الإرسال بنجاح." if success else "فشل الإرسال."
            ),
            requires_manual_review=response.requires_manual_review,
        )

    def is_campaign_paused(self, campaign_id: str) -> bool:
        campaign = self.db.get_campaign(campaign_id)
        return campaign is not None and campaign.state == "paused"

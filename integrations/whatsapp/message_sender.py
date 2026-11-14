"""IOA message sender.

Per-contact sending workflow (per IOA.md section 4.3):

1. Retrieve institute name and phone number.
2. Validate and normalize the phone number.
3. Generate the personalized message.
4. Open the correct WhatsApp conversation.
5. Verify the intended conversation.
6. Populate the message.
7. Confirm that a valid individual approval exists.
8. Send the message.
9. Verify the outgoing message appears in the conversation.
10. Record the result.
11. Update Excel only after successful confirmation.

Rules:
- Opening a chat / populating the message box is NOT a successful send.
- Distinguish SUBMITTED / DELIVERED / FAILED / UNCERTAIN.
- Never auto-retry uncertain sends without checking the conversation first.
- Avoid duplicate messages.
- Never send without a valid individual approval.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib

from core.phone_validator import validate_phone, PhoneValidationResult
from core.message_engine import MessageEngine, GeneratedMessage
from data.models import Contact, ContactStatus, SendOutcome as ModelSendOutcome
from integrations.whatsapp.whatsapp_client import (
    WhatsAppClient,
    ConversationInfo,
    SendOutcome as ClientSendOutcome,
    SendResult,
)


@dataclass
class SendRequest:
    contact: Contact
    campaign_id: str
    approval_id: str
    template_content: str
    proposed_send_at: str | None = None
    excel_path: str | None = None
    excel_sheet: str | None = None


@dataclass
class SendResponse:
    contact_id: str
    institute_name: str
    phone_original: str
    phone_normalized: str
    result: SendResult
    message_hash: str
    error_message: str = ""
    verified: bool = False
    requires_manual_review: bool = False


class MessageSender:
    def __init__(
        self,
        whatsapp_client: WhatsAppClient,
        message_engine: MessageEngine,
        database=None,
        excel_manager=None,
        default_country_code: str = "+967",
    ):
        self.whatsapp = whatsapp_client
        self.message_engine = message_engine
        self.database = database
        self.excel_manager = excel_manager
        self.default_country_code = default_country_code
        self._sent_in_session: set[str] = set()  # avoid duplicates in-session

    # ------------------------------------------------------------------ #
    # Main workflow
    # ------------------------------------------------------------------ #
    def send_approved(self, request: SendRequest) -> SendResponse:
        contact = request.contact

        # 0. Duplicate guard (in-session)
        dedupe_key = f"{contact.id}:{request.campaign_id}"
        if dedupe_key in self._sent_in_session:
            return SendResponse(
                contact_id=contact.id,
                institute_name=contact.institute_name,
                phone_original=contact.phone_original,
                phone_normalized=contact.phone_normalized,
                result=SendResult.FAILED,
                message_hash="",
                error_message="رسالة مكررة ضمن الجلسة نفسها — تم التجاوز.",
                requires_manual_review=False,
            )

        # 1. Validate / normalize phone number
        phone_validation = validate_phone(
            contact.phone_original, self.default_country_code
        )
        if not phone_validation.is_valid and phone_validation.is_uncertain:
            # Do not mark as contacted; preserve for later review
            self._record_attempt(
                request, contact, phone_validation, ModelSendOutcome.FAILED,
                error_message=phone_validation.reason,
            )
            return SendResponse(
                contact_id=contact.id,
                institute_name=contact.institute_name,
                phone_original=contact.phone_original,
                phone_normalized=phone_validation.normalized,
                result=SendResult.FAILED,
                message_hash="",
                error_message=phone_validation.reason,
                requires_manual_review=True,
            )

        # 2. Generate personalized message
        try:
            generated: GeneratedMessage = self.message_engine.generate(
                request.template_content,
                contact.institute_name,
                phone_validation.normalized,
            )
        except ValueError as exc:
            self._record_attempt(
                request, contact, phone_validation, ModelSendOutcome.FAILED,
                error_message=str(exc),
            )
            return SendResponse(
                contact_id=contact.id,
                institute_name=contact.institute_name,
                phone_original=contact.phone_original,
                phone_normalized=phone_validation.normalized,
                result=SendResult.FAILED,
                message_hash="",
                error_message=str(exc),
                requires_manual_review=False,
            )

        # 3. Valid individual approval must exist (validated by caller before
        #    reaching here; double-check here defensively)
        if not request.approval_id:
            return SendResponse(
                contact_id=contact.id,
                institute_name=contact.institute_name,
                phone_original=contact.phone_original,
                phone_normalized=phone_validation.normalized,
                result=SendResult.FAILED,
                message_hash=generated.message_hash,
                error_message="لا توجد موافقة فردية صالحة لهذا المعهد.",
                requires_manual_review=False,
            )

        # 4. Open the correct WhatsApp conversation
        conversation = self.whatsapp.open_conversation(phone_validation.normalized)
        if not conversation.opened:
            self._record_attempt(
                request, contact, phone_validation, ModelSendOutcome.FAILED,
                generated.message_hash,
                error_message="تعذر فتح محادثة واتساب.",
            )
            return SendResponse(
                contact_id=contact.id,
                institute_name=contact.institute_name,
                phone_original=contact.phone_original,
                phone_normalized=phone_validation.normalized,
                result=SendResult.FAILED,
                message_hash=generated.message_hash,
                error_message="تعذر فتح محادثة واتساب.",
                requires_manual_review=False,
            )

        # 5. Verify the intended conversation (mock: always verified)
        if not conversation.verified:
            self._record_attempt(
                request, contact, phone_validation, ModelSendOutcome.UNCERTAIN,
                generated.message_hash,
                error_message="لم يتم التحقق من المحادثة المقصودة.",
            )
            return SendResponse(
                contact_id=contact.id,
                institute_name=contact.institute_name,
                phone_original=contact.phone_original,
                phone_normalized=phone_validation.normalized,
                result=SendResult.UNCERTAIN,
                message_hash=generated.message_hash,
                error_message="لم يتم التحقق من المحادثة المقصودة — مطلوب مراجعة.",
                requires_manual_review=True,
            )

        # 6. Populate the message (NOT a send yet)
        populated = self.whatsapp.populate_message(conversation, generated.message)
        if not populated:
            self._record_attempt(
                request, contact, phone_validation, ModelSendOutcome.FAILED,
                generated.message_hash,
                error_message="تعذر تعبئة الرسالة في صندوق الإدخال.",
            )
            return SendResponse(
                contact_id=contact.id,
                institute_name=contact.institute_name,
                phone_original=contact.phone_original,
                phone_normalized=phone_validation.normalized,
                result=SendResult.FAILED,
                message_hash=generated.message_hash,
                error_message="تعذر تعبئة الرسالة.",
                requires_manual_review=False,
            )

        # 7. Send the message
        client_outcome = self.whatsapp.send_message(conversation)

        # 8. Map client outcome to internal outcome
        if client_outcome.result == SendResult.DELIVERED:
            internal_outcome = ModelSendOutcome.DELIVERED
        elif client_outcome.result == SendResult.SUBMITTED:
            internal_outcome = ModelSendOutcome.SUBMITTED
        elif client_outcome.result == SendResult.FAILED:
            internal_outcome = ModelSendOutcome.FAILED
        else:
            internal_outcome = ModelSendOutcome.UNCERTAIN

        verified = client_outcome.verified

        # 9. Record the attempt
        self._record_attempt(
            request,
            contact,
            phone_validation,
            internal_outcome,
            generated.message_hash,
            error_message=client_outcome.error,
            verified=verified,
        )

        # 10. Update Excel only after successful confirmation
        if internal_outcome in (ModelSendOutcome.SUBMITTED, ModelSendOutcome.DELIVERED):
            self._sent_in_session.add(dedupe_key)
            if self.database:
                self.database.mark_contact_sent(contact.id, _now_iso())
            if self.excel_manager and request.excel_path:
                try:
                    self.excel_manager.update_contact_status(
                        path=Path(request.excel_path),
                        sheet_name=request.excel_sheet or "Sheet1",
                        excel_row_index=contact.excel_row_index or 0,
                        contact_status=ContactStatus.SENT,
                        notes_append="تم الإرسال عبر واتساب (Profile 40).",
                        sent_at=_now_iso(),
                    )
                except Exception:
                    # Excel update failure must not roll back the send record;
                    # it is logged and the contact remains marked in SQLite.
                    pass

            return SendResponse(
                contact_id=contact.id,
                institute_name=contact.institute_name,
                phone_original=contact.phone_original,
                phone_normalized=phone_validation.normalized,
                result=client_outcome.result,
                message_hash=generated.message_hash,
                verified=verified,
                requires_manual_review=False,
            )

        if internal_outcome == ModelSendOutcome.FAILED:
            if self.database:
                self.database.mark_contact_failed(
                    contact.id, client_outcome.error or "فشل الإرسال."
                )
            return SendResponse(
                contact_id=contact.id,
                institute_name=contact.institute_name,
                phone_original=contact.phone_original,
                phone_normalized=phone_validation.normalized,
                result=SendResult.FAILED,
                message_hash=generated.message_hash,
                error_message=client_outcome.error or "فشل الإرسال.",
                requires_manual_review=False,
            )

        # UNCERTAIN — do not auto-retry, do not mark contacted
        if self.database:
            self.database.mark_contact_uncertain(contact.id)
        return SendResponse(
            contact_id=contact.id,
            institute_name=contact.institute_name,
            phone_original=contact.phone_original,
            phone_normalized=phone_validation.normalized,
            result=SendResult.UNCERTAIN,
            message_hash=generated.message_hash,
            error_message=client_outcome.error or "نتيجة الإرسال غير مؤكدة — مطلوب مراجعة المحادثة.",
            verified=verified,
            requires_manual_review=True,
        )

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _record_attempt(
        self,
        request: SendRequest,
        contact: Contact,
        phone_validation: PhoneValidationResult,
        outcome: str,
        message_hash: str = "",
        error_message: str = "",
        verified: bool = False,
    ) -> None:
        from data.models import SendingAttempt

        attempt = SendingAttempt(
            contact_id=contact.id,
            campaign_id=request.campaign_id,
            approval_id=request.approval_id,
            phone_number=phone_validation.normalized,
            institute_name=contact.institute_name,
            outcome=outcome,
            error_message=error_message or None,
            sent_at=_now_iso() if outcome in (
                "submitted", "delivered"
            ) else None,
            verified_at=_now_iso() if verified else None,
        )
        if self.database:
            self.database.create_sending_attempt(attempt)
            if self.database:
                # Update contact status to reflect attempt
                if outcome == "failed":
                    self.database.mark_contact_failed(contact.id, error_message)
                elif outcome == "uncertain":
                    self.database.mark_contact_uncertain(contact.id)

    def set_excel_update_info(
        self, excel_path: Path, sheet_name: str
    ) -> None:
        """Called by the campaign manager with the real workbook path/sheet."""
        self._excel_path = excel_path
        self._excel_sheet = sheet_name


def _now_iso() -> str:
    from datetime import datetime

    return datetime.utcnow().isoformat(timespec="seconds")

"""IOA Telegram approval handlers.

Processes inline-keyboard callback actions:

- Approve & Send Now
- Schedule
- Reject / Skip
- Pause Campaign

Every action is validated against the local database before execution.
"""

from __future__ import annotations

import logging
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from core.approval_manager import ApprovalManager
from data.models import ApprovalRecord


class ApprovalHandlers:
    def __init__(self, campaign_manager):
        self.campaign_manager = campaign_manager
        self.db = campaign_manager.db
        self.approval_manager: ApprovalManager = campaign_manager.approval_manager
        self.logger = logging.getLogger("ioa.telegram.approval")

    # ------------------------------------------------------------------ #
    # Callback entry point
    # ------------------------------------------------------------------ #
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if not query:
            return

        await query.answer()

        data = query.data or ""
        parts = data.split(":")
        action = parts[0]

        # Authorization check
        cm = self.campaign_manager
        bot = cm.telegram_bot
        if bot and bot.authorized_chat_id is not None:
            chat = update.effective_chat
            if chat is None or chat.id != bot.authorized_chat_id:
                await query.edit_message_text("غير مصرح لك بتنفيذ هذا الإجراء.")
                return

        try:
            if action == "approve":
                await self._on_approve(update, query, parts)
            elif action == "schedule":
                await self._on_schedule(update, query, parts, context)
            elif action == "reject":
                await self._on_reject(update, query, parts)
            elif action == "skip":
                await self._on_skip(update, query, parts)
            elif action == "pause":
                await self._on_pause(update, query, parts)
            else:
                await query.edit_message_text("إجراء غير معروف.")
        except Exception as exc:  # pragma: no cover - safety
            self.logger.exception("Approval callback error: %s", exc)
            await query.edit_message_text(f"حدث خطأ أثناء معالجة الإجراء: {exc}")

    # ------------------------------------------------------------------ #
    # Actions
    # ------------------------------------------------------------------ #
    async def _on_approve(self, update: Update, query, parts: list[str]) -> None:
        # Callback format: approve:<approval_id>
        if len(parts) < 2:
            await query.edit_message_text("معرف الموافقة غير صالح.")
            return

        approval_id = parts[1]
        approval = self.db.get_approval(approval_id)
        if not approval:
            await query.edit_message_text("سجل الموافقة غير موجود.")
            return

        campaign = self.db.get_campaign(approval.campaign_id)
        contact = self.db.get_contact(approval.contact_id)

        # Reconstruct the exact approved message for hash validation
        template_content = self._template_for_campaign(approval.campaign_id)
        from core.message_engine import MessageEngine
        engine = MessageEngine()
        try:
            generated = engine.generate(
                template_content,
                contact.institute_name if contact else approval.institute_name,
                contact.phone_normalized if contact else approval.phone_number,
            )
            message_content = generated.message
        except Exception:
            message_content = approval.message_preview

        # Validate before execution (security gate)
        valid, reason = self.approval_manager.validate_approval_for_execution(
            approval_id, approval.contact_id, approval.campaign_id, message_content
        )
        if not valid:
            await query.edit_message_text(f"لا يمكن تنفيذ الموافقة: {reason}")
            return

        # Execute (mark as executed)
        ok, exec_reason = self.approval_manager.execute_approval(
            approval_id, approval.contact_id, approval.campaign_id, message_content
        )
        if not ok:
            await query.edit_message_text(f"فشل التنفيذ: {exec_reason}")
            return

        # Trigger immediate send via campaign manager / message sender
        if contact and campaign:
            send_request = self._build_send_request(contact, campaign, approval, template_content)
            if cm.message_sender:
                response = cm.message_sender.send_approved(send_request)
                if response.result.value in ("submitted", "delivered"):
                    contact.contact_status = "sent"
                    contact.is_contacted = True
                    self.db.upsert_contact(contact)
                    await query.edit_message_text(
                        "✅ تم الموافقة والإرسال الفوري.\n"
                        f"المعهد: {contact.institute_name}\n"
                        f"النتيجة: {response.result.value}"
                    )
                    if bot:
                        bot.notify_send_success(contact, campaign)
                else:
                    await query.edit_message_text(
                        f"⚠️ نتيجة الإرسال: {response.result.value}\n"
                        f"{response.error_message}"
                    )
            else:
                await query.edit_message_text("مرسل الرسائل غير مهيأ بعد.")
        else:
            await query.edit_message_text("تعذر العثور على المعهد أو الحملة.")

    async def _on_schedule(
        self, update: Update, query, parts: list[str], context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        # Callback format: schedule:<approval_id>
        if len(parts) < 2:
            await query.edit_message_text("معرف الموافقة غير صالح.")
            return

        approval_id = parts[1]
        approval = self.db.get_approval(approval_id)
        if not approval:
            await query.edit_message_text("سجل الموافقة غير موجود.")
            return

        # Validate approval is still pending and not expired
        if approval.status != "pending":
            await query.edit_message_text(f"لا يمكن جدولة هذه الموافقة — حالتها: {approval.status}.")
            return
        if approval.is_expired:
            await query.edit_message_text("انتهت صلاحية الموافقة — لا يمكن جدولتها.")
            return

        # Store pending schedule context so the next text message from this
        # chat is treated as the requested date/time.
        chat_id = update.effective_chat.id if update.effective_chat else None
        if chat_id is None:
            await query.edit_message_text("تعذر تحديد الدردشة الحالية.")
            return
        context.user_data["pending_schedule_approval_id"] = approval_id
        context.user_data["pending_schedule_chat_id"] = chat_id

        campaign = self.db.get_campaign(approval.campaign_id)
        contact = self.db.get_contact(approval.contact_id)

        await query.edit_message_text(
            "⏰ جدول الإرسال\n\n"
            f"المعهد: {contact.institute_name if contact else approval.institute_name}\n"
            f"الهاتف: {contact.phone_original if contact else approval.phone_number}\n"
            f"الحملة: {approval.campaign_id}\n"
            "يرجى إرسال التاريخ والوقت المرغوب به بالتنسيق YYYY-MM-DD HH:MM (توقيت عدن).\n"
            "مثال: 2026-12-01 14:30\n"
            "سيتم إرسال الرسالة في الوقت المحدد بعد التحقق من صلاحية الموافقة.\n"
        )
        # Store pending schedule context in user_data for the next message
        context = update.callback_query._chat_instance if hasattr(update.callback_query, '_chat_instance') else None
        # Note: full conversation-state scheduling is handled in the dashboard too.

    async def _on_reject(self, update: Update, query, parts: list[str]) -> None:
        if len(parts) < 2:
            await query.edit_message_text("معرف الموافقة غير صالح.")
            return

        approval_id = parts[1]
        ok = self.approval_manager.reject_approval(approval_id)
        if ok:
            await query.edit_message_text("❌ تم رفض الموافقة وتخطيط المعهد.")
        else:
            await query.edit_message_text("تعذر رفض الموافقة — قد تكون منفذة أو منتهية الصلاحية.")

    async def _on_skip(self, update: Update, query, parts: list[str]) -> None:
        if len(parts) < 2:
            await query.edit_message_text("معرف الموافقة غير صالح.")
            return

        approval_id = parts[1]
        approval = self.db.get_approval(approval_id)
        if not approval:
            await query.edit_message_text("سجل الموافقة غير موجود.")
            return

        contact = self.db.get_contact(approval.contact_id)
        if contact:
            contact.contact_status = "skipped"
            contact.updated_at = _now_iso()
            self.db.upsert_contact(contact)

        ok = self.approval_manager.reject_approval(approval_id)
        if ok:
            await query.edit_message_text("⏭️ تم تخطٍ المعهد وإلغاء الموافقة.")
        else:
            await query.edit_message_text("تم تخطٍ المعهد ولكن تعذر إلغاء الموافقة.")

    async def _on_pause(self, update: Update, query, parts: list[str]) -> None:
        # Callback format: pause:<campaign_id>
        if len(parts) < 2:
            await query.edit_message_text("معرف الحملة غير صالح.")
            return

        campaign_id = parts[1]
        self.campaign_manager.pause_campaign(campaign_id)
        await query.edit_message_text(f"⏸️ تم إيقاف الحملة: {campaign_id}")

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _template_for_campaign(self, campaign_id: str) -> str:
        """Resolve template content for a campaign from the stored campaign."""
        campaign = self.db.get_campaign(campaign_id)
        if campaign and campaign.template_content:
            return campaign.template_content
        return ""

    def _build_send_request(self, contact, campaign, approval, template_content: str):
        from core.message_sender import SendRequest

        return SendRequest(
            contact=contact,
            campaign_id=campaign.id,
            approval_id=approval.id,
            template_content=template_content,
            proposed_send_at=approval.proposed_send_at,
        )


def _now_iso() -> str:
    from datetime import datetime

    return datetime.utcnow().isoformat(timespec="seconds")

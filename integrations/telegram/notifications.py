"""IOA Telegram notifications.

Sends messages to the authorized chat for approval requests, send outcomes,
errors, and campaign events.
"""

from __future__ import annotations

import logging

from data.models import Campaign


class NotificationManager:
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger("ioa.telegram.notifications")

    # ------------------------------------------------------------------ #
    # Internal sender (fire-and-forget, async-safe)
    # ------------------------------------------------------------------ #
    def _send(self, text: str) -> None:
        try:
            import asyncio

            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self.bot._send_text(text))
            else:
                asyncio.run(self.bot._send_text(text))
        except Exception as exc:  # pragma: no cover - best effort
            self.logger.warning("Could not send Telegram notification: %s", exc)

    # ------------------------------------------------------------------ #
    # Notification types
    # ------------------------------------------------------------------ #
    def notify_approval_request(self, approval, contact) -> None:
        text = (
            "📨 طلب موافقة جديد — IOA\n\n"
            f"المعهد: {contact.institute_name}\n"
            f"الهاتف: {contact.phone_original}\n"
            f"الحملة: {approval.campaign_id}\n"
            f"الرسالة: {approval.message_preview}\n"
            f"ملف التعريف: Profile 40\n"
            f"وقت الاقتراح: {approval.proposed_send_at or 'فوراً'}\n"
            f"انتهاء الصلاحية: {approval.expires_at}\n\n"
            "يرجى اختيار إجراء من الأزرار أدناه."
        )
        self._send(text)
        # Inline buttons are attached by the bot handler that receives this
        # notification; here we send the text payload. The approval_handlers
        # module builds the keyboard when the /next or dashboard triggers it.

    def notify_send_success(self, contact, campaign) -> None:
        self._send(
            "✅ تم الإرسال بنجاح — IOA\n\n"
            f"المعهد: {contact.institute_name}\n"
            f"الهاتف: {contact.phone_original}\n"
            f"الحملة: {getattr(campaign, 'id', '')}\n"
            "الواتساب: Profile 40"
        )

    def notify_send_failure(self, contact, campaign, reason: str) -> None:
        self._send(
            "❌ فشل الإرسال — IOA\n\n"
            f"المعهد: {contact.institute_name}\n"
            f"الهاتف: {contact.phone_original}\n"
            f"السبب: {reason}\n"
            "لن يتم إعادة الإرسال تلقائياً."
        )

    def notify_invalid_number(self, contact, reason: str) -> None:
        self._send(
            "⚠️ رقم هاتف غير صالح — IOA\n\n"
            f"المعهد: {contact.institute_name}\n"
            f"الرقم الأصلي: {contact.phone_original}\n"
            f"السبب: {reason}\n"
            "يتطلب مراجعة يدوية."
        )

    def notify_whatsapp_disconnected(self) -> None:
        self._send(
            "🔌 واتساب غير متصل — IOA\n\n"
            "تم اكتشاف انقطاع جلسة واتساب في ملف التعريف 'Profile 40'. "
            "لا يمكن إرسال رسائل جديدة حتى إعادة الاتصال."
        )

    def notify_campaign_started(self, campaign: Campaign) -> None:
        self._send(
            "▶️ بدأ تنفيذ الحملة — IOA\n\n"
            f"اسم الحملة: {campaign.name}\n"
            f"المعرف: {campaign.id}"
        )

    def notify_campaign_paused(self, campaign: Campaign) -> None:
        self._send(
            "⏸️ تم إيقاف الحملة — IOA\n\n"
            f"اسم الحملة: {campaign.name}\n"
            f"المعرف: {campaign.id}"
        )

    def notify_campaign_resumed(self, campaign: Campaign) -> None:
        self._send(
            "▶️ تم استئناف الحملة — IOA\n\n"
            f"اسم الحملة: {campaign.name}\n"
            f"المعرف: {campaign.id}"
        )

    def notify_campaign_completed(self, campaign: Campaign) -> None:
        self._send(
            "🏁 اكتملت الحملة — IOA\n\n"
            f"اسم الحملة: {campaign.name}\n"
            f"المعرف: {campaign.id}"
        )

    def notify_error(self, message: str) -> None:
        self._send(f"⚠️ خطأ في التطبيق — IOA\n\n{message}")

    def notify_shutdown(self) -> None:
        self._send("🛑 تم إيقاف تطبيق IOA محلياً.")

    def notify_startup(self) -> None:
        self._send("🚀 تم تشغيل تطبيق IOA محلياً.")

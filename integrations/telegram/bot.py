"""IOA Telegram Bot — remote control interface for the local application.

Uses python-telegram-bot with polling (suitable for local execution without
a permanent cloud server). Only the authorized Chat ID can send commands or
approvals. The bot token is loaded from settings (environment variable) and
is never hardcoded.
"""

from __future__ import annotations

import logging
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from core.approval_manager import ApprovalManager
from data.models import ApprovalRecord
from integrations.telegram.notifications import NotificationManager
from integrations.telegram.approval_handlers import ApprovalHandlers


class TelegramBot:
    def __init__(
        self,
        token: Optional[str],
        authorized_chat_id: Optional[int],
        campaign_manager,
        settings=None,
    ):
        self.token = token
        self.authorized_chat_id = authorized_chat_id
        self.campaign_manager = campaign_manager
        self.settings = settings
        self.logger = logging.getLogger("ioa.telegram")

        self.notifications = NotificationManager(self)
        self.approval_handlers = ApprovalHandlers(campaign_manager)
        self._application: Optional[Application] = None
        self._running = False

    # ------------------------------------------------------------------ #
    # Authorization
    # ------------------------------------------------------------------ #
    def _is_authorized(self, update: Update) -> bool:
        if self.authorized_chat_id is None:
            return False
        effective_chat = update.effective_chat
        if effective_chat is None:
            return False
        return effective_chat.id == self.authorized_chat_id

    async def _ignore_unauthorized(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_authorized(update):
            self.logger.warning(
                "Unauthorized Telegram user attempted interaction: %s",
                update.effective_chat.id if update.effective_chat else "unknown",
            )
            return

    # ------------------------------------------------------------------ #
    # Commands
    # ------------------------------------------------------------------ #
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_authorized(update):
            return
        await update.effective_message.reply_text(
            "مرحباً بك في بوت IOA —院 outreach automation.\n"
            "الأوامر المتاحة:\n"
            "/status — حالة الحملة والنظام\n"
            "/pause — إيقاف الحملة\n"
            "/resume — استئناف الحملة\n"
            "/next — عرض المؤسسة التالية\n"
            "/skip — تخطٍ للمؤسسة الحالية\n"
            "/help — المساعدة"
        )

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_authorized(update):
            return
        cm = self.campaign_manager
        active = cm.active_campaign_id
        text = f"الحملة النشطة: {active or 'غير محددة'}\n"
        if active:
            stats = cm.get_stats(active)
            text += (
                f"الإجمالي: {stats.total}\n"
                f"قيد الانتظار: {stats.pending}\n"
                "في انتظار الموافقة: {stats.awaiting_approval}\n"
                f"مرسلة: {stats.sent}\n"
                f"فشلت: {stats.failed}\n"
                f"غير مؤكدة: {stats.uncertain}\n"
            )
        # WhatsApp state
        if cm.browser_manager:
            info = cm.browser_manager.mock_connection_info()
            text += f"\nواتساب: {info.state.value}\n"
            text += f"ملف التعريف: Profile 40\n"
        await update.effective_message.reply_text(text)

    async def cmd_pause(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_authorized(update):
            return
        active = self.campaign_manager.active_campaign_id
        if not active:
            await update.effective_message.reply_text("لا توجد حملة نشطة للإيقاف.")
            return
        self.campaign_manager.pause_campaign(active)
        await update.effective_message.reply_text(f"تم إيقاف الحملة: {active}")

    async def cmd_resume(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_authorized(update):
            return
        active = self.campaign_manager.active_campaign_id
        if not active:
            await update.effective_message.reply_text("لا توجد حملة نشطة للاستئناف.")
            return
        self.campaign_manager.resume_campaign(active)
        await update.effective_message.reply_text(f"تم استئناف الحملة: {active}")

    async def cmd_next(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_authorized(update):
            return
        active = self.campaign_manager.active_campaign_id
        if not active:
            await update.effective_message.reply_text("لا توجد حملة نشطة.")
            return
        contacts = self.campaign_manager.get_campaign_contacts(
            active, status="pending"
        )
        if not contacts:
            await update.effective_message.reply_text("لا توجد مؤسسات معلقة في الحملة الحالية.")
            return
        c = contacts[0]
        await update.effective_message.reply_text(
            "المؤسسة التالية:\n"
            f"الاسم: {c.institute_name}\n"
            f"الهاتف: {c.phone_original}\n"
            f"الحالة: {c.contact_status}"
        )

    async def cmd_skip(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_authorized(update):
            return
        await update.effective_message.reply_text(
            "ميزة تخطٍ المؤسسة تتطلب اختياراً من واجهة سطح المكتب."
        )

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_authorized(update):
            return
        await update.effective_message.reply_text(
            "أوامر IOA:\n"
            "/start — بدء البوت\n"
            "/status — عرض الحالة\n"
            "/pause — إيقاف الحملة\n"
            "/resume — استئناف الحملة\n"
            "/next — التالية\n"
            "/skip — تخطٍ\n"
            "/help — هذه الرسالة"
        )

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    def start_polling(self) -> None:
        """Start the Telegram polling loop (blocking). Call from a thread."""
        if not self.token:
            self.logger.error("Telegram bot token is not configured.")
            return
        if self._running:
            return

        application = Application.builder().token(self.token).build()

        # Command handlers (authorized only via middleware-style check)
        application.add_handler(CommandHandler("start", self.cmd_start))
        application.add_handler(CommandHandler("status", self.cmd_status))
        application.add_handler(CommandHandler("pause", self.cmd_pause))
        application.add_handler(CommandHandler("resume", self.cmd_resume))
        application.add_handler(CommandHandler("next", self.cmd_next))
        application.add_handler(CommandHandler("skip", self.cmd_skip))
        application.add_handler(CommandHandler("help", self.cmd_help))

        # Callback query handler for inline approval buttons
        application.add_handler(
            CallbackQueryHandler(self.approval_handlers.handle_callback)
        )

        # Ignore unauthorized messages
        application.add_handler(
            MessageHandler(filters.ALL, self._ignore_unauthorized), group=99
        )

        self._application = application
        self._running = True
        self.logger.info("Telegram bot polling started")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        self._running = False

    def stop(self) -> None:
        self._running = False
        if self._application:
            self._application.stop_running()

    # ------------------------------------------------------------------ #
    # Notification helpers (delegated)
    # ------------------------------------------------------------------ #
    async def _send_text(self, text: str) -> None:
        if not self._application or self.authorized_chat_id is None:
            return
        try:
            # Use the bot instance to send directly
            bot = self._application.bot
            import asyncio
            asyncio.create_task(bot.send_message(chat_id=self.authorized_chat_id, text=text))
        except Exception as exc:  # pragma: no cover
            self.logger.exception("Failed to send Telegram notification: %s", exc)

    # Public sync wrappers used by other components (fire-and-forget logging)
    def notify_approval_request(self, approval: ApprovalRecord, contact) -> None:
        self.notifications.notify_approval_request(approval, contact)

    def notify_send_success(self, contact, campaign) -> None:
        self.notifications.notify_send_success(contact, campaign)

    def notify_send_failure(self, contact, campaign, reason: str) -> None:
        self.notifications.notify_send_failure(contact, campaign, reason)

    def notify_invalid_number(self, contact, reason: str) -> None:
        self.notifications.notify_invalid_number(contact, reason)

    def notify_whatsapp_disconnected(self) -> None:
        self.notifications.notify_whatsapp_disconnected()

    def notify_campaign_started(self, campaign: Campaign) -> None:
        self.notifications.notify_campaign_started(campaign)

    def notify_campaign_paused(self, campaign: Campaign) -> None:
        self.notifications.notify_campaign_paused(campaign)

    def notify_campaign_resumed(self, campaign: Campaign) -> None:
        self.notifications.notify_campaign_resumed(campaign)

    def notify_campaign_completed(self, campaign: Campaign) -> None:
        self.notifications.notify_campaign_completed(campaign)

    def notify_error(self, message: str) -> None:
        self.notifications.notify_error(message)

    def notify_shutdown(self) -> None:
        self.notifications.notify_shutdown()

    def notify_startup(self) -> None:
        self.notifications.notify_startup()


# Avoid circular import: Campaign is imported lazily in notifications
from data.models import Campaign  # noqa: E402

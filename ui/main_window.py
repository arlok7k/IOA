"""IOA main window — professional desktop dashboard (PySide6).

Supports Arabic RTL layout and English LTR. Sections:
1. Dashboard
2. Contacts
3. Campaigns
4. Message Template
5. WhatsApp Settings (Profile 40 only — no profile selection)
6. Telegram Settings
7. Scheduler
8. Activity Logs
9. Build & System Information

Long-running operations (browser, Telegram, Excel) run in worker threads so
the UI never blocks.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QThread, QObject, Signal, Slot, QSize
from PySide6.QtGui import QFont, QIcon, QAction
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QListWidget, QListWidgetItem, QLabel, QFrame, QSplitter,
    QMessageBox, QStatusBar, QApplication,
)

from config.settings import AppSettings
from data.database import Database
from core.campaign_manager import CampaignManager
from integrations.whatsapp.browser_manager import BrowserManager
from integrations.telegram.bot import TelegramBot


class WorkerSignals(QObject):
    finished = Signal(object)
    error = Signal(str)
    progress = Signal(str)


class BaseWorker(QObject):
    """Run a callable in a QThread without blocking the UI."""
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
            self.signals.finished.emit(result)
        except Exception as exc:  # pragma: no cover - worker safety
            self.signals.error.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(
        self,
        settings: AppSettings,
        database: Database,
        campaign_manager: CampaignManager,
        browser_manager: BrowserManager,
        telegram_bot: TelegramBot,
    ):
        super().__init__()
        self.settings = settings
        self.database = database
        self.campaign_manager = campaign_manager
        self.browser_manager = browser_manager
        self.telegram_bot = telegram_bot

        self.setWindowTitle(f"{settings.APP_NAME} v{settings.APP_VERSION}")
        self.resize(1200, 800)

        self._setup_font()
        self._build_ui()
        self._apply_rtl(settings.language)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("جاري التحضير..." if settings.language == "ar" else "Ready")

        # Thread pool for background workers
        self._active_threads: list[QThread] = []

    # ------------------------------------------------------------------ #
    # UI construction
    # ------------------------------------------------------------------ #
    def _setup_font(self) -> None:
        font = QFont("Segoe UI", 10)
        if self.settings.language == "ar":
            font = QFont("Segoe UI", 10)
        QApplication.setFont(font)

    def _apply_rtl(self, language: str) -> None:
        if language == "ar":
            self.setLayoutDirection(Qt.RightToLeft)
        else:
            self.setLayoutDirection(Qt.LeftToRight)

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Sidebar navigation
        self.nav_list = QListWidget()
        self.nav_list.setFixedWidth(220)
        self.nav_list.setStyleSheet("""
            QListWidget {
                background: #1f2937;
                color: #e5e7eb;
                border: none;
                font-size: 14px;
                padding-top: 12px;
            }
            QListWidget::item {
                padding: 14px 18px;
                border-bottom: 1px solid #374151;
            }
            QListWidget::item:selected {
                background: #2563eb;
                color: #ffffff;
            }
            QListWidget::item:hover {
                background: #374151;
            }
        """)

        nav_items = [
            ("dashboard", "لوحة التحكم", "Dashboard"),
            ("contacts", "جهات الاتصال", "Contacts"),
            ("campaigns", "الحملات", "Campaigns"),
            ("template", "قالب الرسالة", "Message Template"),
            ("whatsapp", "إعدادات واتساب", "WhatsApp Settings"),
            ("telegram", "إعدادات تليجرام", "Telegram Settings"),
            ("scheduler", "المجدول", "Scheduler"),
            ("logs", "سجلات الأنشطة", "Activity Logs"),
            ("info", "معلومات النظام", "System Info"),
        ]
        for key, ar, en in nav_items:
            label = ar if self.settings.language == "ar" else en
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, key)
            self.nav_list.addItem(item)
        self.nav_list.currentRowChanged.connect(self._on_nav_changed)

        # Stacked pages
        self.pages = QStackedWidget()
        self.pages.addWidget(self._build_dashboard_page())
        self.pages.addWidget(self._build_contacts_page())
        self.pages.addWidget(self._build_campaigns_page())
        self.pages.addWidget(self._build_template_page())
        self.pages.addWidget(self._build_whatsapp_settings_page())
        self.pages.addWidget(self._build_telegram_settings_page())
        self.pages.addWidget(self._build_scheduler_page())
        self.pages.addWidget(self._build_logs_page())
        self.pages.addWidget(self._build_info_page())

        root.addWidget(self.nav_list)
        root.addWidget(self.pages)

        self.nav_list.setCurrentRow(0)

    # ------------------------------------------------------------------ #
    # Navigation
    # ------------------------------------------------------------------ #
    def _on_nav_changed(self, row: int) -> None:
        if row < 0:
            return
        item = self.nav_list.item(row)
        key = item.data(Qt.UserRole)
        index_map = {
            "dashboard": 0, "contacts": 1, "campaigns": 2, "template": 3,
            "whatsapp": 4, "telegram": 5, "scheduler": 6, "logs": 7, "info": 8,
        }
        self.pages.setCurrentIndex(index_map.get(key, 0))

    # ------------------------------------------------------------------ #
    # Pages (placeholders wired to real modules progressively)
    # ------------------------------------------------------------------ #
    def _section_header(self, title_ar: str, title_en: str) -> QWidget:
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background: #111827;
                color: #ffffff;
                padding: 16px 24px;
                font-size: 18px;
                font-weight: bold;
            }
        """)
        label = QLabel(title_ar if self.settings.language == "ar" else title_en)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(label)
        return frame

    def _card(self, title: str, value: str, subtitle: str = "") -> QFrame:
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: #ffffff;
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                padding: 16px;
            }
        """)
        v = QVBoxLayout(card)
        v.setContentsMargins(12, 12, 12, 12)
        t = QLabel(title)
        t.setStyleSheet("color: #6b7280; font-size: 12px; font-weight: bold;")
        val = QLabel(value)
        val.setStyleSheet("color: #111827; font-size: 22px; font-weight: bold;")
        sub = QLabel(subtitle)
        sub.setStyleSheet("color: #9ca3af; font-size: 11px;")
        v.addWidget(t)
        v.addWidget(val)
        v.addWidget(sub)
        return card

    def _build_dashboard_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(self._section_header("لوحة التحكم", "Dashboard"))

        # Stats cards row
        stats_row = QHBoxLayout()
        self.card_total = self._card("إجمالي المعاهد", "0", "Total institutes")
        self.card_pending = self._card("قيد الانتظار", "0", "Pending")
        self.card_awaiting = self._card("في انتظار الموافقة", "0", "Awaiting approval")
        self.card_sent = self._card("مرسلة بنجاح", "0", "Sent")
        self.card_failed = self._card("فشلت", "0", "Failed")
        self.card_uncertain = self._card("غير مؤكدة", "0", "Uncertain")
        for card in (self.card_total, self.card_pending, self.card_awaiting,
                     self.card_sent, self.card_failed, self.card_uncertain):
            stats_row.addWidget(card)
        layout.addLayout(stats_row)

        # Connection status
        conn_frame = QFrame()
        conn_frame.setStyleSheet("""
            QFrame {
                background: #f9fafb;
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                padding: 16px;
            }
        """)
        cl = QVBoxLayout(conn_frame)
        self.lbl_whatsapp_status = QLabel("واتساب: غير متصل")
        self.lbl_telegram_status = QLabel("تليجرام: غير مضبط")
        self.lbl_profile = QLabel("ملف التعريف: Profile 40")
        for lbl in (self.lbl_whatsapp_status, self.lbl_telegram_status, self.lbl_profile):
            lbl.setStyleSheet("font-size: 13px; color: #374151;")
            cl.addWidget(lbl)
        layout.addWidget(conn_frame)

        layout.addStretch()
        return page

    def _build_contacts_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(self._section_header("جهات الاتصال", "Contacts"))
        info = QLabel(
            "عرض، بحث، تصفية، وتفتيش المعاهد من ملف Excel.\n"
            "يتم تحميل البيانات من مجلد الإدخال المحدد في الإعدادات."
        )
        info.setStyleSheet("color: #6b7280; padding: 12px;")
        layout.addWidget(info)
        layout.addStretch()
        return page

    def _build_campaigns_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(self._section_header("الحملات", "Campaigns"))
        info = QLabel(
            "إنشاء، بدء، إيقاف، استئناف، ومراجعة الحملات.\n"
            "كل حملة تتطلب موافقات فردية عبر تليجرام قبل الإرسال."
        )
        info.setStyleSheet("color: #6b7280; padding: 12px;")
        layout.addWidget(info)
        layout.addStretch()
        return page

    def _build_template_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(self._section_header("قالب الرسالة", "Message Template"))
        info = QLabel(
            "عرض قالب TXT ومعاينة الرسائل المخصصة.\n"
            "يتم استبدال العنصر {{institute_name}} فقط دون تعديل نص القالب الأصلي."
        )
        info.setStyleSheet("color: #6b7280; padding: 12px;")
        layout.addWidget(info)
        layout.addStretch()
        return page

    def _build_whatsapp_settings_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(self._section_header("إعدادات واتساب", "WhatsApp Settings"))

        info = QFrame()
        info.setStyleSheet("background: #ffffff; border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px;")
        il = QVBoxLayout(info)
        self.lbl_wp_profile = QLabel("اسم الملف التعريفي: Profile 40")
        self.lbl_wp_path = QLabel(
            r"C:\Users\USERW\AppData\Local\Google\Chrome\User Data\Profile 40"
        )
        self.lbl_wp_state = QLabel("حالة الاتصال: غير منفذ بعد")
        self.lbl_wp_auth = QLabel("حالة المصادقة: غير مؤكدة")
        for lbl in (self.lbl_wp_profile, self.lbl_wp_path, self.lbl_wp_state, self.lbl_wp_auth):
            lbl.setStyleSheet("font-size: 13px; color: #111827; padding: 4px 0;")
            il.addWidget(lbl)
        layout.addWidget(info)

        note = QLabel(
            "ملاحظة هامة: يستخدم تطبيق IOA حصراً ملف تعريف كروم 'Profile 40' المسار الثابت.\n"
            "لا يوجد اختيار لملف تعريف آخر، ولا اكتشاف تلقائي، ولا اتخاذ ملف تعريف بديل."
        )
        note.setStyleSheet("color: #dc2626; font-size: 12px; padding: 12px; background: #fef2f2; border-radius: 6px; border: 1px solid #fee2e2;")
        layout.addWidget(note)

        btn_refresh = self._make_button("تحديث حالة واتساب", self._refresh_whatsapp_status)
        layout.addWidget(btn_refresh)
        layout.addStretch()
        return page

    def _build_telegram_settings_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(self._section_header("إعدادات تليجرام", "Telegram Settings"))
        info = QLabel(
            "توكن البوت ومعرف الدردشة المخول يُضبطان عبر ملف .env على الجهاز المحلي.\n"
            "لا تُرمَّز الأسرار في الكود المصدر."
        )
        info.setStyleSheet("color: #6b7280; padding: 12px;")
        layout.addWidget(info)
        layout.addStretch()
        return page

    def _build_scheduler_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(self._section_header("المجدول", "Scheduler"))
        info = QLabel(
            "ضبط التواريخ والأوقات والفواصل الزمنية وحدود التنفيذ.\n"
            "جميع التوقيتات تستخدم منطقة زمنية Asia/Aden (عدن)."
        )
        info.setStyleSheet("color: #6b7280; padding: 12px;")
        layout.addWidget(info)
        layout.addStretch()
        return page

    def _build_logs_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(self._section_header("سجلات الأنشطة", "Activity Logs"))
        info = QLabel(
            "عرض سجل الإرسال، الفشل، وأحداث النظام.\n"
            "يتم حفظ السجلات محلياً في مجلد logs."
        )
        info.setStyleSheet("color: #6b7280; padding: 12px;")
        layout.addWidget(info)
        layout.addStretch()
        return page

    def _build_info_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(self._section_header("معلومات النظام", "Build & System Information"))
        info = QLabel(
            f"الإصدار: {self.settings.APP_VERSION}\n"
            f"قاعدة البيانات: SQLite (محلية)\n"
            f"المنطقة الزمنية: {getattr(self.settings, 'timezone', 'Asia/Aden')}\n"
            "يتم تخزين جميع البيانات محلياً على جهاز Windows."
        )
        info.setStyleSheet("color: #6b7280; padding: 12px;")
        layout.addWidget(info)
        layout.addStretch()
        return page

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _make_button(self, text: str, slot) -> QWidget:
        from PySide6.QtWidgets import QPushButton
        btn = QPushButton(text)
        btn.setStyleSheet("""
            QPushButton {
                background: #2563eb;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 10px 16px;
                font-size: 13px;
            }
            QPushButton:hover {
                background: #1d4ed8;
            }
            QPushButton:pressed {
                background: #1e40af;
            }
        """)
        btn.clicked.connect(slot)
        return btn

    def _refresh_whatsapp_status(self) -> None:
        """Refresh WhatsApp connection state in a background thread."""
        self.lbl_wp_state.setText("حالة الاتصال: جاري التحقق...")
        self._run_worker(self.browser_manager.connect, self._on_whatsapp_checked)

    def _on_whatsapp_checked(self, result) -> None:
        if result:
            self.lbl_wp_state.setText(f"حالة الاتصال: {result.state.value}")
            self.lbl_wp_auth.setText(
                "حالة المصادقة: " + ("موثقة" if result.is_authenticated else "غير موثقة")
            )
            self.status_bar.showMessage("تم التحقق من واتساب")
        else:
            self.lbl_wp_state.setText("حالة الاتصال: خطأ")
            self.status_bar.showMessage("تعذر التحقق من واتساب")

    # ------------------------------------------------------------------ #
    # Background worker runner
    # ------------------------------------------------------------------ #
    def _run_worker(self, fn, on_finished, *args, **kwargs) -> None:
        worker = BaseWorker(fn, *args, **kwargs)
        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.signals.finished.connect(lambda r: self._finish_thread(thread, on_finished, r))
        worker.signals.error.connect(lambda e: self._finish_thread(thread, lambda: None, e, error=True))
        self._active_threads.append(thread)
        thread.start()

    def _finish_thread(self, thread: QThread, on_finished, result, error: bool = False) -> None:
        thread.quit()
        thread.wait()
        if thread in self._active_threads:
            self._active_threads.remove(thread)
        if error:
            QMessageBox.warning(self, "تحذير", f"حدث خطأ: {result}")
        else:
            on_finished(result)

    def closeEvent(self, event) -> None:
        # Stop background threads gracefully
        for thread in self._active_threads:
            thread.quit()
            thread.wait()
        if self.telegram_bot:
            self.telegram_bot.stop()
        event.accept()

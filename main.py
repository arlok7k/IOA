"""IOA — Institute Outreach Automation.

Application entry point.

Local-first Windows desktop application for WhatsApp outreach to training
institutes, with individual approvals via Telegram Bot.

Cloud development note: actual Chrome Profile 40 / WhatsApp Web integration
is verified on the user's Windows machine. Cloud tests use mocks.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Ensure the repository root is on sys.path when run directly
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QCoreApplication, QLocale
from PySide6.QtWidgets import QApplication, QMessageBox

from config.settings import AppSettings
from ui.main_window import MainWindow
from data.database import Database
from core.campaign_manager import CampaignManager
from integrations.whatsapp.browser_manager import BrowserManager
from integrations.telegram.bot import TelegramBot


def setup_logging(logs_dir: str = "logs") -> None:
    """Configure application-wide logging (console + rotating file)."""
    import logging.handlers

    log_path = Path(logs_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    log_file = log_path / "ioa.log"

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    )

    # Console handler (INFO+)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)

    # Rotating file handler (DEBUG+)
    fh = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)

    logger.addHandler(ch)
    logger.addHandler(fh)

    logging.getLogger("ioa").info("Logging initialized")


def load_settings() -> AppSettings:
    """Load application settings from environment / .env."""
    try:
        from dotenv import load_dotenv

        env_path = ROOT / ".env"
        if env_path.exists():
            load_dotenv(env_path)
    except Exception:  # pragma: no cover - python-dotenv optional in cloud
        pass
    return AppSettings.from_env()


def main() -> int:
    """Bootstrap and run the IOA desktop application."""
    settings = load_settings()
    setup_logging(settings.storage.logs_dir)

    logger = logging.getLogger("ioa.main")
    logger.info("Starting %s v%s", settings.APP_NAME, settings.APP_VERSION)

    app = QApplication(sys.argv)
    app.setApplicationName(settings.APP_NAME)
    app.setOrganizationName(settings.APP_ORGANIZATION)
    app.setOrganizationDomain(settings.APP_DOMAIN)
    app.setApplicationVersion(settings.APP_VERSION)

    # RTL layout support for Arabic
    if settings.language == "ar":
        locale = QLocale(QLocale.Arabic, QLocale.SaudiArabia)
        QLocale.setDefault(locale)
        app.setLayoutDirection(
            __import__("PySide6.QtCore", fromlist=["Qt"]).Qt.RightToLeft
        )
    else:
        app.setLayoutDirection(
            __import__("PySide6.QtCore", fromlist=["Qt"]).Qt.LeftToRight
        )

    # Initialize local SQLite database
    # Use app_data_dir if set (for Windows EXE runs where install dir may not be writable)
    storage = settings.storage
    if storage.app_data_dir:
        db_path = Path(storage.app_data_dir) / "database" / "ioa.db"
        backups_dir = Path(storage.app_data_dir) / "backups"
        logs_dir = Path(storage.app_data_dir) / "logs"
    else:
        db_path = ROOT / storage.database_file
        backups_dir = ROOT / storage.backups_dir
        logs_dir = ROOT / storage.logs_dir
    db_path.parent.mkdir(parents=True, exist_ok=True)
    database = Database(str(db_path))
    database.initialize()

    # Initialize core components (lazy, no hardware access at startup)
    browser_manager = BrowserManager(
        user_data_dir=settings.chrome_user_data_dir,
        profile_directory=settings.chrome_profile_directory,
        profile_path=settings.chrome_profile_path,
    )
    campaign_manager = CampaignManager(database=database, settings=settings)
    telegram_bot = TelegramBot(
        token=settings.telegram_bot_token,
        authorized_chat_id=settings.authorized_chat_id,
        campaign_manager=campaign_manager,
        settings=settings,
    )

    # Wire components together
    campaign_manager.set_browser_manager(browser_manager)
    campaign_manager.set_telegram_bot(telegram_bot)

    # Create and show the main window
    window = MainWindow(
        settings=settings,
        database=database,
        campaign_manager=campaign_manager,
        browser_manager=browser_manager,
        telegram_bot=telegram_bot,
    )
    window.show()

    logger.info("Application shell ready")
    return app.exec()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # pragma: no cover - top-level safety
        logging.getLogger("ioa").exception("Fatal error: %s", exc)
        try:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Critical)
            msg.setWindowTitle("IOA — خطأ فادح")
            msg.setText(f"حدث خطأ غير متوقع:\n{exc}")
            msg.exec()
        except Exception:
            pass
        sys.exit(1)

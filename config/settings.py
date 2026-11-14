r"""IOA — Institute Outreach Automation.
Application configuration.

Fixed Chrome Profile 40 configuration (MUST NOT CHANGE):
CHROME_USER_DATA_DIR = r"C:\Users\USERW\AppData\Local\Google\Chrome\User Data"
CHROME_PROFILE_DIRECTORY = "Profile 40"
CHROME_PROFILE_PATH = r"C:\Users\USERW\AppData\Local\Google\Chrome\User Data\Profile 40"

All sensitive credentials (Telegram bot token, authorized chat ID) are loaded
from environment variables or a local .env file and must never be hardcoded.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final


# ---------------------------------------------------------------------------
# Fixed Chrome Profile 40 configuration (per IOA.md — never change)
# ---------------------------------------------------------------------------
CHROME_USER_DATA_DIR: Final[str] = r"C:\Users\USERW\AppData\Local\Google\Chrome\User Data"
CHROME_PROFILE_DIRECTORY: Final[str] = "Profile 40"
CHROME_PROFILE_PATH: Final[str] = (
    r"C:\Users\USERW\AppData\Local\Google\Chrome\User Data\Profile 40"
)

# ---------------------------------------------------------------------------
# Default input directory (Windows)
# ---------------------------------------------------------------------------
DEFAULT_INPUT_DIRECTORY: Final[str] = r"C:\Users\USERW\Desktop\qoder_file_con\contect - Copy"

# ---------------------------------------------------------------------------
# Default message placeholder (configurable)
# ---------------------------------------------------------------------------
DEFAULT_MESSAGE_PLACEHOLDER: Final[str] = "{{institute_name}}"

# ---------------------------------------------------------------------------
# Timezone for all scheduling (Asia/Aden = UTC+3)
# ---------------------------------------------------------------------------
APP_TIMEZONE: Final[str] = "Asia/Aden"

# ---------------------------------------------------------------------------
# Default country code for Yemen (+967) — used as fallback for local numbers
# ---------------------------------------------------------------------------
DEFAULT_COUNTRY_CODE: Final[str] = "+967"

# ---------------------------------------------------------------------------
# Application metadata
# ---------------------------------------------------------------------------
APP_NAME: Final[str] = "IOA — Institute Outreach Automation"
APP_VERSION: Final[str] = "1.0.0"
APP_ORGANIZATION: Final[str] = "IOA"
APP_DOMAIN: Final[str] = "ioa.local"

# ---------------------------------------------------------------------------
# Storage paths (local-first; relative to the application installation dir)
# ---------------------------------------------------------------------------
@dataclass
class StoragePaths:
    database_file: str = "storage/database/ioa.db"
    backups_dir: str = "storage/backups"
    logs_dir: str = "logs"
    app_data_dir: str = ""  # If set, overrides relative paths for Windows EXE runs


# ---------------------------------------------------------------------------
# Runtime settings loaded from environment / .env
# ---------------------------------------------------------------------------
@dataclass
class AppSettings:
    """Application settings resolved at startup.

    Telegram credentials are intentionally NOT hardcoded — they come from
    environment variables or a local .env file kept on the user's machine.
    """

    # Telegram
    telegram_bot_token: str | None = None
    authorized_chat_id: int | None = None

    # Input directory (Windows path)
    input_directory: str = DEFAULT_INPUT_DIRECTORY

    # Chrome profile (fixed)
    chrome_user_data_dir: str = CHROME_USER_DATA_DIR
    chrome_profile_directory: str = CHROME_PROFILE_DIRECTORY
    chrome_profile_path: str = CHROME_PROFILE_PATH

    # Message placeholder
    message_placeholder: str = DEFAULT_MESSAGE_PLACEHOLDER

    # Timezone
    timezone: str = APP_TIMEZONE

    # Default country code
    default_country_code: str = DEFAULT_COUNTRY_CODE

    # Campaign scheduling defaults
    campaign_start_date: str | None = None
    campaign_start_time: str | None = None
    message_interval_seconds: int = 60
    max_messages_per_session: int = 50
    allowed_sending_start_hour: int = 9
    allowed_sending_end_hour: int = 17

    # UI
    language: str = "ar"  # ar / en

    storage: StoragePaths = field(default_factory=StoragePaths)

    @classmethod
    def from_env(cls) -> "AppSettings":
        """Load settings from environment variables with safe defaults."""
        import os

        def _env_int(name: str, default: int) -> int:
            try:
                return int(os.getenv(name, str(default)))
            except (TypeError, ValueError):
                return default

        authorized_chat_id = None
        raw_chat_id = os.getenv("IOA_TELEGRAM_CHAT_ID")
        if raw_chat_id:
            try:
                authorized_chat_id = int(raw_chat_id.strip())
            except ValueError:
                authorized_chat_id = None

        return cls(
            telegram_bot_token=os.getenv("IOA_TELEGRAM_BOT_TOKEN"),
            authorized_chat_id=authorized_chat_id,
            input_directory=os.getenv("IOA_INPUT_DIRECTORY", DEFAULT_INPUT_DIRECTORY),
            chrome_user_data_dir=os.getenv(
                "IOA_CHROME_USER_DATA_DIR", CHROME_USER_DATA_DIR
            ),
            chrome_profile_directory=os.getenv(
                "IOA_CHROME_PROFILE_DIRECTORY", CHROME_PROFILE_DIRECTORY
            ),
            chrome_profile_path=os.getenv(
                "IOA_CHROME_PROFILE_PATH", CHROME_PROFILE_PATH
            ),
            message_placeholder=os.getenv(
                "IOA_MESSAGE_PLACEHOLDER", DEFAULT_MESSAGE_PLACEHOLDER
            ),
            timezone=os.getenv("IOA_TIMEZONE", APP_TIMEZONE),
            default_country_code=os.getenv(
                "IOA_DEFAULT_COUNTRY_CODE", DEFAULT_COUNTRY_CODE
            ),
            message_interval_seconds=_env_int(
                "IOA_MESSAGE_INTERVAL_SECONDS", 60
            ),
            max_messages_per_session=_env_int(
                "IOA_MAX_MESSAGES_PER_SESSION", 50
            ),
            allowed_sending_start_hour=_env_int(
                "IOA_SENDING_START_HOUR", 9
            ),
            allowed_sending_end_hour=_env_int(
                "IOA_SENDING_END_HOUR", 17
            ),
            language=os.getenv("IOA_LANGUAGE", "ar"),
        )

    def is_telegram_configured(self) -> bool:
        return bool(self.telegram_bot_token and self.authorized_chat_id is not None)

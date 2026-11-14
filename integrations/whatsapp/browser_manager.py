"""IOA browser manager.

Launches/attaches WhatsApp Web exclusively through Chrome Profile 40.
Cloud-development mode uses simulated/mocked browser behavior because the
cloud environment does not contain the user's Chrome Profile 40 or
authenticated WhatsApp session. Actual browser integration is verified on
the user's Windows machine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import os
import platform


class ConnectionState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    AUTHENTICATED = "authenticated"
    QR_REQUIRED = "qr_required"
    EXPIRED = "expired"
    ERROR = "error"


@dataclass
class WhatsAppConnectionInfo:
    state: ConnectionState = ConnectionState.DISCONNECTED
    profile_name: str = "Profile 40"
    profile_path: str = ""
    account_label: str = ""
    qr_code_visible: bool = False
    last_error: str = ""
    last_checked: str = ""

    @property
    def is_authenticated(self) -> bool:
        return self.state == ConnectionState.AUTHENTICATED

    @property
    def needs_qr(self) -> bool:
        return self.state == ConnectionState.QR_REQUIRED


class BrowserManager:
    """Manages the Chrome + WhatsApp Web session bound to Profile 40."""

    def __init__(
        self,
        user_data_dir: str,
        profile_directory: str,
        profile_path: str,
    ):
        self.user_data_dir = user_data_dir
        self.profile_directory = profile_directory
        self.profile_path = profile_path
        self.state = WhatsAppConnectionInfo(
            profile_name=profile_directory,
            profile_path=profile_path,
        )
        self._browser_process = None  # subprocess handle (local Windows only)
        self._playwright_page = None  # real browser page (local Windows only)
        self._mock_mode = not _is_windows()

    # ------------------------------------------------------------------ #
    # Profile verification (no browser launch)
    # ------------------------------------------------------------------ #
    def verify_profile_exists(self) -> tuple[bool, str]:
        """Return (ok, message) — does NOT launch Chrome."""
        p = Path(self.profile_path)
        if not p.exists():
            return False, (
                f"ملف التعريف 'Profile 40' غير موجود: {self.profile_path}"
            )
        udd = Path(self.user_data_dir)
        if not udd.exists():
            return False, f"دليل بيانات مستخدم كروم غير موجود: {self.user_data_dir}"
        return True, "ملف التعريف 'Profile 40' موجود وجاهز."

    def detect_lock(self) -> tuple[bool, str]:
        """Return (locked, message) by checking the Lock file only."""
        lock = Path(self.profile_path) / "Lock"
        if lock.exists():
            return True, (
                "ملف التعريف 'Profile 40' مقفل بواسطة جلسة كروم مفتوحة. "
                "أغلق كروم ثم أعد المحاولة."
            )
        return False, "لا يوجد قفل على ملف التعريف."

    # ------------------------------------------------------------------ #
    # Connection lifecycle (real implementation stubbed for cloud)
    # ------------------------------------------------------------------ #
    def connect(self) -> WhatsAppConnectionInfo:
        """Attempt to connect WhatsApp Web via Profile 40.

        In the cloud environment this runs in simulated mode and reports
        DISCONNECTED with a note that local verification is required.
        """
        self.state.state = ConnectionState.CONNECTING
        self.state.last_checked = _now_iso()

        exists, msg = self.verify_profile_exists()
        if not exists:
            self.state.state = ConnectionState.ERROR
            self.state.last_error = msg
            return self.state

        locked, lock_msg = self.detect_lock()
        if locked:
            self.state.state = ConnectionState.ERROR
            self.state.last_error = lock_msg
            return self.state

        if self._mock_mode:
            # Simulated cloud behavior — NOT actual WhatsApp verification.
            self.state.state = ConnectionState.DISCONNECTED
            self.state.last_error = (
                "وضع المحاكاة (السحابة): لم يتم التحقق الفعلي من واتساب. "
                "سيتم التحقق على جهاز Windows المحلي باستخدام Profile 40."
            )
            self.state.qr_code_visible = True
            return self.state

        # --- Real Windows implementation (placeholder for local build) ---
        # Here the actual Chrome/Playwright/Selenium launch would occur,
        # using ONLY self.user_data_dir and self.profile_directory.
        self.state.state = ConnectionState.DISCONNECTED
        self.state.last_error = "التنفيذ المحلي لمتصفح كروم لم يتم تفعيله بعد في هذه النسخة."
        return self.state

    def disconnect(self) -> None:
        self.state.state = ConnectionState.DISCONNECTED
        self.state.qr_code_visible = False
        self.state.last_error = ""

    def refresh_state(self) -> WhatsAppConnectionInfo:
        """Re-check WhatsApp authentication state without sending."""
        # In real implementation: inspect WhatsApp Web DOM for auth indicators.
        return self.state

    def is_authenticated(self) -> bool:
        return self.state.is_authenticated

    def mock_set_authenticated(self, authenticated: bool = True) -> None:
        """Test-only helper to simulate authentication state in the cloud."""
        self.state.state = (
            ConnectionState.AUTHENTICATED if authenticated else ConnectionState.DISCONNECTED
        )
        self.state.qr_code_visible = not authenticated

    def mock_connection_info(self) -> WhatsAppConnectionInfo:
        return self.state


def _is_windows() -> bool:
    return platform.system().lower() == "windows"


def _now_iso() -> str:
    from datetime import datetime

    return datetime.utcnow().isoformat(timespec="seconds")

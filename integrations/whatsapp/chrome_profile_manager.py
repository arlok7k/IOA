r"""IOA Chrome Profile 40 manager.

CRITICAL (per IOA.md): The application MUST exclusively use the existing
Chrome Profile 40. No profile discovery, no selection, no switching, no
fallback to other profiles, no cookie copying, no session extraction.

Fixed configuration (MUST NOT CHANGE):
  CHROME_USER_DATA_DIR = r"C:\Users\USERW\AppData\Local\Google\Chrome\User Data"
  CHROME_PROFILE_DIRECTORY = "Profile 40"
  CHROME_PROFILE_PATH  = r"C:\Users\USERW\AppData\Local\Google\Chrome\User Data\Profile 40"
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import platform


@dataclass(frozen=True)
class ChromeProfileConfig:
    user_data_dir: str
    profile_directory: str
    profile_path: str

    @property
    def exists(self) -> bool:
        return Path(self.profile_path).exists() and Path(
            self.user_data_dir
        ).exists()

    @property
    def lock_file(self) -> Path:
        return Path(self.profile_path) / "Lock"


@dataclass
class ProfileStatus:
    exists: bool
    locked: bool
    path: str
    message: str


# Fixed configuration per IOA.md — never altered at runtime
FIXED_PROFILE = ChromeProfileConfig(
    user_data_dir=r"C:\Users\USERW\AppData\Local\Google\Chrome\User Data",
    profile_directory="Profile 40",
    profile_path=r"C:\Users\USERW\AppData\Local\Google\Chrome\User Data\Profile 40",
)


class ChromeProfileManager:
    """Validates and monitors the fixed Profile 40 directory."""

    def __init__(self, config: ChromeProfileConfig = FIXED_PROFILE):
        self.config = config

    def verify_profile(self) -> ProfileStatus:
        """Check that Profile 40 exists and report lock conflicts."""
        profile_path = Path(self.config.profile_path)
        user_data_dir = Path(self.config.user_data_dir)

        if not user_data_dir.exists():
            return ProfileStatus(
                exists=False,
                locked=False,
                path=str(self.config.profile_path),
                message=(
                    "دليل بيانات المستخدم لمتصفح كروم غير موجود: "
                    f"{user_data_dir}"
                ),
            )

        if not profile_path.exists():
            return ProfileStatus(
                exists=False,
                locked=False,
                path=str(self.config.profile_path),
                message=(
                    "ملف التعريف 'Profile 40' غير موجود في المسار المحدد: "
                    f"{self.config.profile_path}"
                ),
            )

        locked = self._is_locked()
        if locked:
            return ProfileStatus(
                exists=True,
                locked=True,
                path=str(self.config.profile_path),
                message=(
                    "ملف التعريف 'Profile 40' مقفل (يوجد ملف Lock). "
                    "يُغلقusually عند تشغيل كروم باستخدام هذا الملف التعريفي. "
                    "أغلق نوافذ كروم التي تستخدم 'Profile 40' ثم أعد المحاولة."
                ),
            )

        return ProfileStatus(
            exists=True,
            locked=False,
            path=str(self.config.profile_path),
            message="ملف التعريف 'Profile 40' جاهز للاستخدام.",
        )

    def _is_locked(self) -> bool:
        """Detect a Chrome profile lock without touching any Chrome process."""
        lock = self.config.lock_file
        if not lock.exists():
            return False
        # A lock file that is very old (stale) may be safe to ignore,
        # but per requirements we never delete it or force Chrome to close.
        return True

    def detect_lock(self) -> tuple[bool, str]:
        """Return (locked, message) by checking the Lock file only."""
        lock = self.config.lock_file
        if lock.exists():
            return True, (
                "ملف التعريف مقفل بواسطة جلسة كروم مفتوحة. "
                "أغلق كروم ثم أعد المحاولة."
            )
        return False, "لا يوجد قفل على ملف التعريف."

    def lock_conflict_instructions(self) -> str:
        return (
            "إجراءات الإصلاح الآمنة عند قفل ملف التعريف 'Profile 40':\n"
            "1. تأكد من إغلاق جميع نوافذ متصفح كروم التي تستخدم 'Profile 40'.\n"
            "2. تأكد من عدم وجود أي عملية كروم مفتوحة في الخلفية تستخدم نفس ملف التعريف.\n"
            "3. أغلق كروم entièrement ثم أعد تشغيل تطبيق IOA.\n"
            "4. لا تحذف ملف 'Lock' يدوياً ولا تنهِ عمليات كروم بالقوة.\n"
            "المسار: " + self.config.profile_path
        )

    def is_windows(self) -> bool:
        return platform.system().lower() == "windows"

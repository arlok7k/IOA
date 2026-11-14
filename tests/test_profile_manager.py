"""Tests for Chrome Profile 40 manager (IOA phase 3)."""

import os
import tempfile
from pathlib import Path

import pytest

from integrations.whatsapp.chrome_profile_manager import (
    ChromeProfileConfig, ChromeProfileManager, FIXED_PROFILE,
)


def test_fixed_profile_constants():
    assert FIXED_PROFILE.profile_directory == "Profile 40"
    assert FIXED_PROFILE.user_data_dir.endswith("\\User Data")
    assert FIXED_PROFILE.profile_path.endswith("\\Profile 40")


def test_verify_profile_missing_in_cloud():
    # Cloud environment does not have the real Windows path
    mgr = ChromeProfileManager()
    status = mgr.verify_profile()
    assert status.exists is False
    assert "Profile 40" in status.message or "كروم" in status.message


def test_verify_profile_exists(tmp_path):
    profile_dir = tmp_path / "User Data" / "Profile 40"
    profile_dir.mkdir(parents=True)
    config = ChromeProfileConfig(
        user_data_dir=str(tmp_path / "User Data"),
        profile_directory="Profile 40",
        profile_path=str(profile_dir),
    )
    mgr = ChromeProfileManager(config)
    status = mgr.verify_profile()
    assert status.exists is True
    assert status.locked is False


def test_detect_lock_file(tmp_path):
    profile_dir = tmp_path / "User Data" / "Profile 40"
    profile_dir.mkdir(parents=True)
    (profile_dir / "Lock").write_text("lock")
    config = ChromeProfileConfig(
        user_data_dir=str(tmp_path / "User Data"),
        profile_directory="Profile 40",
        profile_path=str(profile_dir),
    )
    mgr = ChromeProfileManager(config)
    locked, msg = mgr.detect_lock()
    assert locked is True
    assert "مقفل" in msg or "lock" in msg.lower()


def test_lock_conflict_instructions_mention_profile40():
    mgr = ChromeProfileManager()
    instr = mgr.lock_conflict_instructions()
    assert "Profile 40" in instr

"""Tests for Telegram approval handlers (IOA phase 5)."""

import pytest

from data.database import Database
from data.models import Contact, ContactStatus, Campaign, CampaignState, ApprovalRecord
from core.approval_manager import ApprovalManager
from integrations.telegram.approval_handlers import ApprovalHandlers


class FakeCampaignManager:
    def __init__(self, db):
        self.db = db
        self.telegram_bot = None
        self.message_sender = None
        self.approval_manager = ApprovalManager(db)


@pytest.fixture
def handlers():
    import tempfile, os
    path = tempfile.mktemp(suffix=".db")
    db = Database(path)
    db.initialize()
    cm = FakeCampaignManager(db)
    h = ApprovalHandlers(cm)
    yield h, db
    db.close()
    for ext in ("", "-wal", "-shm"):
        p = path + ext
        if os.path.exists(p):
            os.remove(p)


def _make_contact(db, institute="معهد", phone="+967771234567"):
    c = Contact(institute_name=institute, phone_original=phone, phone_normalized=phone)
    return db.upsert_contact(c)


def _make_campaign(db, template_content=""):
    camp = Campaign(name="ح", state=CampaignState.ACTIVE, template_content=template_content)
    return db.create_campaign(camp)


def test_template_for_campaign_returns_stored_template(handlers):
    h, db = handlers
    cid = _make_contact(db)
    campid = _make_campaign(db, template_content="مرحبا {{institute_name}}")
    result = h._template_for_campaign(campid)
    assert result == "مرحبا {{institute_name}}"


def test_template_for_campaign_returns_empty_when_no_template(handlers):
    h, db = handlers
    cid = _make_contact(db)
    campid = _make_campaign(db, template_content="")
    result = h._template_for_campaign(campid)
    assert result == ""


def test_approve_validation_rejects_modified_message(handlers):
    h, db = handlers
    cid = _make_contact(db)
    campid = _make_campaign(db, template_content="مرحبا {{institute_name}}")

    # Create approval with original message
    appr = ApprovalRecord(
        contact_id=cid, campaign_id=campid,
        message_hash="", message_preview="مرحبا معهد",
        institute_name="معهد", phone_number="+967771234567",
        status="pending",
    )
    # Compute hash for original message
    import hashlib
    original_msg = "مرحبا معهد"
    appr.message_hash = hashlib.sha256(original_msg.encode("utf-8")).hexdigest()
    db.create_approval(appr)

    # Validate with modified message -> should fail
    ok, reason = h.approval_manager.validate_approval_for_execution(
        appr.id, cid, campid, "رسالة معدلة"
    )
    assert ok is False
    assert "تغير" in reason or "تعدل" in reason


def test_approve_validation_accepts_matching_message(handlers):
    h, db = handlers
    cid = _make_contact(db)
    campid = _make_campaign(db, template_content="مرحبا {{institute_name}}")

    import hashlib
    from datetime import datetime, timedelta
    original_msg = "مرحبا معهد"
    expires_at = (datetime.utcnow() + timedelta(hours=1)).isoformat(timespec="seconds")
    appr = ApprovalRecord(
        contact_id=cid, campaign_id=campid,
        message_hash=hashlib.sha256(original_msg.encode("utf-8")).hexdigest(),
        message_preview="مرحبا معهد",
        institute_name="معهد", phone_number="+967771234567",
        status="pending", expires_at=expires_at,
    )
    db.create_approval(appr)

    ok, reason = h.approval_manager.validate_approval_for_execution(
        appr.id, cid, campid, original_msg
    )
    assert ok is True


def test_approve_twice_prevented_idempotent(handlers):
    h, db = handlers
    cid = _make_contact(db)
    campid = _make_campaign(db)

    import hashlib
    from datetime import datetime, timedelta
    expires_at = (datetime.utcnow() + timedelta(hours=1)).isoformat(timespec="seconds")
    appr = ApprovalRecord(
        contact_id=cid, campaign_id=campid,
        message_hash=hashlib.sha256("msg".encode("utf-8")).hexdigest(),
        message_preview="msg",
        institute_name="معهد", phone_number="+967771234567",
        status="pending", expires_at=expires_at,
    )
    aid = db.create_approval(appr)

    ok1, _ = h.approval_manager.execute_approval(aid, cid, campid, "msg")
    assert ok1 is True

    ok2, reason = h.approval_manager.execute_approval(aid, cid, campid, "msg")
    assert ok2 is False
    assert "غير صالحة" in reason or "executed" in reason

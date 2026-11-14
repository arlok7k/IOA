"""Tests for the approval manager (IOA phase 5)."""

import pytest

from data.database import Database
from data.models import Contact, ContactStatus, Campaign, CampaignState
from core.approval_manager import ApprovalManager, ApprovalRequest


@pytest.fixture
def mgr():
    import tempfile, os
    path = tempfile.mktemp(suffix=".db")
    db = Database(path)
    db.initialize()
    am = ApprovalManager(db)
    yield am, db
    db.close()
    for ext in ("", "-wal", "-shm"):
        p = path + ext
        if os.path.exists(p):
            os.remove(p)


def _make_contact(db, institute="معهد", phone="+967771234567"):
    c = Contact(institute_name=institute, phone_original=phone, phone_normalized=phone)
    return db.upsert_contact(c)


def _make_campaign(db):
    camp = Campaign(name="ح", state=CampaignState.ACTIVE)
    return db.create_campaign(camp)


def test_create_approval(mgr):
    am, db = mgr
    cid = _make_contact(db)
    campid = _make_campaign(db)
    req = ApprovalRequest(
        contact=db.get_contact(cid),
        campaign_id=campid,
        message_content="مرحبا {{institute_name}}",
        ttl_minutes=60,
    )
    appr = am.create_approval(req)
    assert appr.status == "pending"
    assert appr.contact_id == cid
    assert appr.campaign_id == campid
    assert len(appr.message_hash) == 64


def test_validate_approval_valid(mgr):
    am, db = mgr
    cid = _make_contact(db)
    campid = _make_campaign(db)
    appr = am.create_approval(ApprovalRequest(
        contact=db.get_contact(cid), campaign_id=campid,
        message_content="مرحبا معهد",
    ))
    ok, reason = am.validate_approval_for_execution(
        appr.id, cid, campid, "مرحبا معهد"
    )
    assert ok is True


def test_validate_wrong_contact(mgr):
    am, db = mgr
    cid1 = _make_contact(db, "أ")
    cid2 = _make_contact(db, "ب")
    campid = _make_campaign(db)
    appr = am.create_approval(ApprovalRequest(
        contact=db.get_contact(cid1), campaign_id=campid,
        message_content="msg",
    ))
    ok, reason = am.validate_approval_for_execution(
        appr.id, cid2, campid, "msg"
    )
    assert ok is False


def test_validate_wrong_campaign(mgr):
    am, db = mgr
    cid = _make_contact(db)
    campid = _make_campaign(db)
    appr = am.create_approval(ApprovalRequest(
        contact=db.get_contact(cid), campaign_id=campid,
        message_content="msg",
    ))
    ok, reason = am.validate_approval_for_execution(
        appr.id, cid, "other-campaign", "msg"
    )
    assert ok is False


def test_validate_modified_message(mgr):
    am, db = mgr
    cid = _make_contact(db)
    campid = _make_campaign(db)
    appr = am.create_approval(ApprovalRequest(
        contact=db.get_contact(cid), campaign_id=campid,
        message_content="الرسالة الأصلية",
    ))
    ok, reason = am.validate_approval_for_execution(
        appr.id, cid, campid, "الرسالة المعدلة"
    )
    assert ok is False
    assert "تغير" in reason or "تعدل" in reason


def test_execute_approval_idempotent(mgr):
    am, db = mgr
    cid = _make_contact(db)
    campid = _make_campaign(db)
    appr = am.create_approval(ApprovalRequest(
        contact=db.get_contact(cid), campaign_id=campid,
        message_content="msg",
    ))
    ok1, _ = am.execute_approval(appr.id, cid, campid, "msg")
    assert ok1 is True
    ok2, reason = am.execute_approval(appr.id, cid, campid, "msg")
    assert ok2 is False


def test_reject_approval(mgr):
    am, db = mgr
    cid = _make_contact(db)
    campid = _make_campaign(db)
    appr = am.create_approval(ApprovalRequest(
        contact=db.get_contact(cid), campaign_id=campid,
        message_content="msg",
    ))
    assert am.reject_approval(appr.id) is True
    loaded = db.get_approval(appr.id)
    assert loaded.status == "rejected"

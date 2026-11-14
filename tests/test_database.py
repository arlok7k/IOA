"""Tests for the SQLite database layer (IOA phase 1)."""

import os
import tempfile

import pytest

from data.database import Database
from data.models import (
    Contact, ContactStatus, Campaign, CampaignState, ApprovalRecord,
    SendingAttempt, ErrorLog,
)


@pytest.fixture
def db():
    path = tempfile.mktemp(suffix=".db")
    database = Database(path)
    database.initialize()
    yield database
    database.close()
    for ext in ("", "-wal", "-shm"):
        p = path + ext
        if os.path.exists(p):
            os.remove(p)


def test_initialize_creates_tables(db):
    assert db is not None


def test_contact_upsert_and_get(db):
    c = Contact(
        institute_name="معهد الاختبار",
        phone_original="771234567",
        phone_normalized="+967771234567",
        address="صنعاء",
        contact_status=ContactStatus.PENDING,
    )
    cid = db.upsert_contact(c)
    got = db.get_contact(cid)
    assert got is not None
    assert got.institute_name == "معهد الاختبار"
    assert got.phone_normalized == "+967771234567"
    assert got.is_contacted is False


def test_contact_mark_sent(db):
    c = Contact(institute_name="م", phone_original="1", phone_normalized="+1")
    cid = db.upsert_contact(c)
    db.mark_contact_sent(cid, "2026-01-01T12:00:00")
    got = db.get_contact(cid)
    assert got.contact_status == ContactStatus.SENT
    assert got.is_contacted is True


def test_campaign_crud(db):
    camp = Campaign(name="حملة", state=CampaignState.DRAFT)
    cid = db.create_campaign(camp)
    loaded = db.get_campaign(cid)
    assert loaded.name == "حملة"
    assert loaded.state == CampaignState.DRAFT


def test_approval_crud_and_expiry(db):
    c = Contact(institute_name="م", phone_original="1", phone_normalized="+1")
    cid = db.upsert_contact(c)
    camp = Campaign(name="حملة", state=CampaignState.ACTIVE)
    campid = db.create_campaign(camp)
    appr = ApprovalRecord(
        contact_id=cid, campaign_id=campid, message_hash="h",
        message_preview="p", institute_name="م", phone_number="+1",
        status="pending",
    )
    aid = db.create_approval(appr)
    loaded = db.get_approval(aid)
    assert loaded.status == "pending"
    # No expiry set -> considered expired by model
    assert loaded.is_expired is True


def test_sending_attempt(db):
    c = Contact(institute_name="م", phone_original="1", phone_normalized="+1")
    cid = db.upsert_contact(c)
    camp = Campaign(name="حملة", state=CampaignState.ACTIVE)
    campid = db.create_campaign(camp)
    att = SendingAttempt(
        contact_id=cid, campaign_id=campid, phone_number="+1",
        institute_name="م", outcome="submitted",
    )
    atid = db.create_sending_attempt(att)
    attempts = db.list_attempts_for_contact(cid)
    assert len(attempts) == 1
    assert attempts[0].outcome == "submitted"


def test_error_log(db):
    eid = db.log_error(" boom ", source="test")
    logs = db.list_error_logs(limit=5)
    assert len(logs) == 1
    assert logs[0].message == " boom "


def test_config_get_set(db):
    db.set_config("k", "v")
    assert db.get_config("k") == "v"
    assert db.get_config("missing", "DEFAULT") == "DEFAULT"


def test_execution_lock_acquire_release(db):
    assert db.acquire_lock("lock1", "holder1", ttl_seconds=60) is True
    # Second acquire should fail (lock held)
    assert db.acquire_lock("lock1", "holder2", ttl_seconds=60) is False
    db.release_lock("lock1")
    assert db.acquire_lock("lock1", "holder2", ttl_seconds=60) is True
    db.release_lock("lock1")


def test_list_contacts_filter(db):
    for i in range(3):
        c = Contact(institute_name=f"م{i}", phone_original=str(i), phone_normalized=f"+{i}")
        db.upsert_contact(c)
    allc = db.list_contacts()
    assert len(allc) == 3

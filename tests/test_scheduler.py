"""Tests for the campaign scheduler (IOA phase 6)."""

from datetime import datetime, timedelta

from data.database import Database
from data.models import Contact, ContactStatus, Campaign, CampaignState
from core.scheduler import Scheduler


class FakeCampaignManager:
    def __init__(self, db, contacts):
        self.db = db
        self.contacts = contacts
        self.active_campaign_id = None
        self._campaign = None

    def get_campaign(self, campaign_id):
        return self._campaign

    def get_template_for_contact(self, contact_id):
        return "مرحبا {{institute_name}}"


class FakeMessageSender:
    def __init__(self):
        self.calls = []

    def send_approved(self, request):
        self.calls.append(request.contact.id)
        from core.message_sender import SendResponse
        from integrations.whatsapp.whatsapp_client import SendResult
        return SendResponse(
            contact_id=request.contact.id,
            institute_name=request.contact.institute_name,
            phone_original=request.contact.phone_original,
            phone_normalized=request.contact.phone_normalized,
            result=SendResult.SUBMITTED,
            message_hash="h",
        )


def test_scheduler_skips_paused_campaign():
    import tempfile, os
    path = tempfile.mktemp(suffix=".db")
    db = Database(path)
    db.initialize()
    try:
        camp = Campaign(name="ح", state=CampaignState.PAUSED)
        cid = db.create_campaign(camp)
        cm = FakeCampaignManager(db, [])
        cm._campaign = camp
        cm.active_campaign_id = cid
        sched = Scheduler(db, cm)
        sched.config.campaign_id = cid
        res = sched.tick("2026-01-01T10:00:00")
        assert res.get("skipped_paused") == 1
    finally:
        db.close()
        for ext in ("", "-wal", "-shm"):
            p = path + ext
            if os.path.exists(p):
                os.remove(p)


def test_scheduler_skips_outside_hours():
    import tempfile, os
    path = tempfile.mktemp(suffix=".db")
    db = Database(path)
    db.initialize()
    try:
        camp = Campaign(
            name="ح", state=CampaignState.ACTIVE,
            sending_start_hour=9, sending_end_hour=17,
        )
        cid = db.create_campaign(camp)
        cm = FakeCampaignManager(db, [])
        cm._campaign = camp
        cm.active_campaign_id = cid
        sched = Scheduler(db, cm)
        sched.config.campaign_id = cid
        # 20:00 is outside allowed hours
        res = sched.tick("2026-01-01T20:00:00")
        assert res.get("skipped_outside_hours") == 1
    finally:
        db.close()
        for ext in ("", "-wal", "-shm"):
            p = path + ext
            if os.path.exists(p):
                os.remove(p)


def test_scheduler_skips_already_contacted():
    import tempfile, os
    path = tempfile.mktemp(suffix=".db")
    db = Database(path)
    db.initialize()
    try:
        camp = Campaign(name="ح", state=CampaignState.ACTIVE)
        cid = db.create_campaign(camp)
        contact = Contact(
            institute_name="م", phone_original="1", phone_normalized="+1",
            contact_status=ContactStatus.SENT, is_contacted=True, campaign_id=cid,
        )
        db.upsert_contact(contact)
        from data.models import SchedulingRecord
        rec = __import__("data.models", fromlist=["SchedulingRecord"]).SchedulingRecord(
            campaign_id=cid, contact_id=contact.id,
            scheduled_at="2026-01-01T10:00:00", status="pending",
        )
        db.create_scheduling_record(rec)
        cm = FakeCampaignManager(db, [contact])
        cm._campaign = camp
        cm.active_campaign_id = cid
        sched = Scheduler(db, cm)
        sched.config.campaign_id = cid
        res = sched.tick("2026-01-01T10:00:00")
        assert res.get("skipped_contacted") == 1
    finally:
        db.close()
        for ext in ("", "-wal", "-shm"):
            p = path + ext
            if os.path.exists(p):
                os.remove(p)

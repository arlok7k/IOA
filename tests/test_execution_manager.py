"""Tests for the execution manager (IOA phase 6)."""

from data.models import Contact, ContactStatus
from core.execution_manager import ExecutionManager
from integrations.whatsapp.message_sender import SendResponse
from integrations.whatsapp.whatsapp_client import SendResult


class FakeDB:
    def __init__(self):
        self.contacts = {}
        self.campaigns = {}

    def get_contact(self, cid):
        return self.contacts.get(cid)

    def get_campaign(self, cid):
        return self.campaigns.get(cid)

    def get_approval_by_contact_and_campaign(self, contact_id, campaign_id):
        return getattr(self, "_approval", None)

    def upsert_contact(self, contact):
        self.contacts[contact.id] = contact


class FakeSender:
    def __init__(self, outcome="submitted", error=""):
        self.outcome = outcome
        self.error = error
        self.calls = []

    def send_approved(self, request):
        self.calls.append(request)
        return SendResponse(
            contact_id=request.contact.id,
            institute_name=request.contact.institute_name,
            phone_original=request.contact.phone_original,
            phone_normalized=request.contact.phone_normalized,
            result=SendResult(self.outcome),
            message_hash="h",
            error_message=self.error,
            requires_manual_review=(self.outcome == "uncertain"),
        )


class FakeApprovalManager:
    pass


def test_execution_skips_already_contacted():
    db = FakeDB()
    c = Contact(institute_name="م", phone_original="1", phone_normalized="+1",
                contact_status=ContactStatus.SENT, is_contacted=True)
    db.contacts[c.id] = c
    em = ExecutionManager(db, FakeSender(), FakeApprovalManager())
    res = em.execute_send(c, "camp", "مرحبا {{institute_name}}")
    assert res.success is False
    assert res.result == "skipped"
    assert "تجاوز" in res.message


def test_execution_requires_approval():
    db = FakeDB()
    c = Contact(institute_name="م", phone_original="1", phone_normalized="+1")
    db.contacts[c.id] = c
    em = ExecutionManager(db, FakeSender(), FakeApprovalManager())
    res = em.execute_send(c, "camp", "مرحبا {{institute_name}}")
    assert res.success is False
    assert res.result == "no_approval"


def test_execution_success():
    db = FakeDB()
    c = Contact(institute_name="معهد", phone_original="1", phone_normalized="+1")
    db.contacts[c.id] = c
    db._approval = type("A", (), {"status": "pending", "is_expired": False,
                                  "id": "a1", "proposed_send_at": None})()
    sender = FakeSender(outcome="submitted")
    em = ExecutionManager(db, sender, FakeApprovalManager())
    res = em.execute_send(c, "camp", "مرحبا {{institute_name}}")
    assert res.success is True
    assert res.result == SendResult.SUBMITTED
    assert len(sender.calls) == 1

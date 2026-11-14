"""IOA WhatsApp Web client interface.

Defines the contract for opening conversations, populating messages, sending,
and verifying outgoing messages. Real browser automation (local Windows) and
test doubles (cloud) implement this interface.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class SendResult(Enum):
    SUBMITTED = "submitted"   # message submitted successfully in WhatsApp
    DELIVERED = "delivered"   # reliable delivery evidence available
    FAILED = "failed"         # send failed
    UNCERTAIN = "uncertain"   # outcome could not be confirmed


@dataclass
class ConversationInfo:
    phone_number: str
    institute_name: str
    opened: bool = False
    verified: bool = False  # conversation matches the intended contact


@dataclass
class SendOutcome:
    result: SendResult
    message: str
    error: str = ""
    verified: bool = False  # outgoing message confirmed visible in conversation


class WhatsAppClient:
    """Abstract WhatsApp Web integration bound to a single Chrome profile."""

    def __init__(self, profile_path: str):
        self.profile_path = profile_path

    def open_conversation(self, phone_number: str) -> ConversationInfo:
        """Open the WhatsApp chat for the given phone number."""
        raise NotImplementedError

    def populate_message(self, conversation: ConversationInfo, text: str) -> bool:
        """Type the message into the WhatsApp input box (NOT a send)."""
        raise NotImplementedError

    def send_message(self, conversation: ConversationInfo) -> SendOutcome:
        """Send the populated message and verify it appears in the conversation."""
        raise NotImplementedError

    def is_authenticated(self) -> bool:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError


class WhatsAppClientMock(WhatsAppClient):
    """Test double for cloud development — simulates WhatsApp Web behavior."""

    def __init__(self, profile_path: str, simulate_auth: bool = True):
        super().__init__(profile_path)
        self.simulate_auth = simulate_auth
        self.opened_conversations: dict[str, ConversationInfo] = {}
        self.populated: dict[str, str] = {}
        self.sent: list[tuple[str, str]] = []  # (phone, message)
        self.send_behavior: SendResult = SendResult.SUBMITTED

    def is_authenticated(self) -> bool:
        return self.simulate_auth

    def open_conversation(self, phone_number: str) -> ConversationInfo:
        conv = ConversationInfo(
            phone_number=phone_number,
            institute_name="",
            opened=True,
            verified=True,
        )
        self.opened_conversations[phone_number] = conv
        return conv

    def populate_message(self, conversation: ConversationInfo, text: str) -> bool:
        self.populated[conversation.phone_number] = text
        return True

    def send_message(self, conversation: ConversationInfo) -> SendOutcome:
        self.sent.append((conversation.phone_number, self.populated.get(
            conversation.phone_number, ""
        )))
        return SendOutcome(
            result=self.send_behavior,
            message="رسالة مرسلة (محاكاة).",
            verified=True,
        )

    def close(self) -> None:
        pass

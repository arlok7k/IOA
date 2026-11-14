"""Tests for the message template engine (IOA phase 2)."""

import pytest

from core.message_engine import MessageEngine, DEFAULT_PLACEHOLDER


class FakePath:
    def __init__(self, text):
        self._text = text

    def read_text(self, encoding="utf-8"):
        return self._text


def test_load_template_preserves_utf8_and_linebreaks():
    engine = MessageEngine()
    text = "السلام عليكم {{institute_name}}\nسطر ثاني\nسطر ثالث"
    result = engine.load_template(FakePath(text))
    assert result.has_placeholder is True
    assert result.is_empty is False
    assert "{{institute_name}}" in result.content
    assert "\n" in result.content


def test_generate_replaces_only_placeholder():
    engine = MessageEngine()
    msg = engine.generate(
        "مرحبا {{institute_name}}، أهلاً بك.",
        "معهد المستقبل",
        "+967771234567",
    )
    assert msg.message == "مرحبا معهد المستقبل، أهلاً بك."
    assert msg.institute_name == "معهد المستقبل"
    assert msg.phone_number == "+967771234567"
    assert len(msg.message_hash) == 64  # SHA-256 hex


def test_generate_preserves_original_when_no_placeholder():
    engine = MessageEngine()
    msg = engine.generate("رسالة ثابتة بدون عنصر نائب.", "أي معهد", "+1")
    assert msg.message == "رسالة ثابتة بدون عنصر نائب."


def test_generate_raises_on_empty_institute():
    engine = MessageEngine()
    with pytest.raises(ValueError):
        engine.generate("مرحبا {{institute_name}}", "", "+1")


def test_generate_raises_on_empty_result():
    engine = MessageEngine()
    with pytest.raises(ValueError):
        engine.generate("", "معهد", "+1")


def test_detect_missing_placeholder():
    engine = MessageEngine()
    assert engine.detect_missing_placeholder("{{institute_name}} مرحباً") is False
    assert engine.detect_missing_placeholder("مرحباً فقط") is True


def test_default_placeholder():
    assert DEFAULT_PLACEHOLDER == "{{institute_name}}"

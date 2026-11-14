"""Tests for the Yemen phone number validator (IOA phase 2)."""

import pytest

from core.phone_validator import validate_phone, DEFAULT_COUNTRY_CODE


def test_yemen_local_number_gets_country_code():
    r = validate_phone("771234567")
    assert r.normalized == "+967771234567"
    assert r.is_valid is True
    assert r.is_uncertain is False


def test_yemen_international_not_modified():
    r = validate_phone("+967771234567")
    assert r.normalized == "+967771234567"
    assert r.is_valid is True


def test_foreign_number_kept_as_is():
    r = validate_phone("+1234567890")
    assert r.normalized == "+1234567890"
    assert r.is_valid is True


def test_empty_number_uncertain():
    r = validate_phone("")
    assert r.is_valid is False
    assert r.is_uncertain is True
    assert r.reason != ""


def test_00_prefix_converted_to_plus():
    r = validate_phone("00967771234567")
    assert r.normalized == "+967771234567"
    assert r.is_valid is True


def test_unknown_local_prefix_uncertain():
    r = validate_phone("123456789")
    assert r.is_uncertain is True


def test_default_country_code_is_yemen():
    assert DEFAULT_COUNTRY_CODE == "+967"

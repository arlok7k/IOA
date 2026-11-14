"""IOA phone number validator.

Default country code: Yemen (+967).

Rules:
- Do not add +967 to numbers that already carry a valid international prefix.
- Validate the number before use.
- Do not guess unclear numbers — mark them for manual review.
- Keep the original number in Excel; store the normalized form internally.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


DEFAULT_COUNTRY_CODE = "+967"
YEMEN_MOBILE_PREFIXES = ("77", "71", "70", "73", "78")  # common Yemen mobile prefixes


@dataclass
class PhoneValidationResult:
    original: str
    normalized: str          # E.164-like internal representation, e.g. +967771234567
    is_valid: bool
    is_uncertain: bool       # True when the number looks plausible but unverified
    reason: str = ""         # human-readable reason when invalid/uncertain


def _digits_only(text: str) -> str:
    return re.sub(r"\D", "", text)


def validate_phone(
    phone: str,
    default_country_code: str = DEFAULT_COUNTRY_CODE,
) -> PhoneValidationResult:
    """Validate and normalize a phone number.

    - If the number already starts with '+' followed by digits -> treat as
      international (no default country code added).
    - If it starts with '00' -> convert to '+'.
    - If it is a local Yemeni number (9 digits starting with a mobile prefix)
      -> prefix with +967.
    - Otherwise -> uncertain (manual review).
    """
    original = phone.strip()
    if not original:
        return PhoneValidationResult(
            original=original,
            normalized="",
            is_valid=False,
            is_uncertain=True,
            reason="الرقم فارغ.",
        )

    digits = _digits_only(original)

    # Already international (starts with +)
    if original.startswith("+"):
        if len(digits) < 7:
            return PhoneValidationResult(
                original=original,
                normalized=original,
                is_valid=False,
                is_uncertain=True,
                reason="رقم دولي قصير جداً.",
            )
        return PhoneValidationResult(
            original=original,
            normalized=original,
            is_valid=True,
            is_uncertain=False,
        )

    # Starts with 00 -> international
    if digits.startswith("00"):
        normalized = "+" + digits[2:]
        if len(digits) < 9:
            return PhoneValidationResult(
                original=original,
                normalized=normalized,
                is_valid=False,
                is_uncertain=True,
                reason="رقم دولي قصير بعد إزالة 00.",
            )
        return PhoneValidationResult(
            original=original,
            normalized=normalized,
            is_valid=True,
            is_uncertain=False,
        )

    # Local number without country code
    # Yemen mobile numbers are 9 digits starting with 77/71/70/73/78
    if len(digits) == 9 and digits[:2] in YEMEN_MOBILE_PREFIXES:
        normalized = default_country_code + digits
        return PhoneValidationResult(
            original=original,
            normalized=normalized,
            is_valid=True,
            is_uncertain=False,
        )

    # Local 9 digits but unknown prefix -> uncertain
    if len(digits) == 9:
        return PhoneValidationResult(
            original=original,
            normalized=default_country_code + digits,
            is_valid=True,
            is_uncertain=True,
            reason="رقم محلي 9 أرباعاً مع بادئة غير معروفة — يتطلب مراجعة يدوية.",
        )

    # Anything else -> uncertain
    return PhoneValidationResult(
        original=original,
        normalized=default_country_code + digits if digits else "",
        is_valid=False,
        is_uncertain=True,
        reason="صيغة رقم غير واضحة — يتطلب مراجعة يدوية.",
    )

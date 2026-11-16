"""Indian phone number normalisation to E.164 (+91XXXXXXXXXX)."""

from __future__ import annotations

import re

from app.core.errors import ValidationFailed

_DIGITS = re.compile(r"\D+")


def normalize_indian_phone(raw: str) -> str:
    """Normalise common Indian formats to E.164.

    Accepts: 9876543210, 09876543210, +91 98765 43210, 91-9876543210, 0091 9876543210.
    Indian mobile numbers are 10 digits beginning with 6-9.
    """
    if raw is None:
        raise ValidationFailed("Phone number is required")
    digits = _DIGITS.sub("", raw)
    if digits.startswith("0091"):
        digits = digits[4:]
    elif digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    elif digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]
    if len(digits) != 10 or digits[0] not in "6789":
        raise ValidationFailed("Invalid Indian mobile number", code="INVALID_PHONE")
    return "+91" + digits


def to_wa_id(e164: str) -> str:
    """WhatsApp IDs are the E.164 number without '+'."""
    return e164.lstrip("+")


def from_wa_id(wa_id: str) -> str | None:
    try:
        return normalize_indian_phone(wa_id)
    except ValidationFailed:
        return None


def mask_phone(e164: str | None) -> str:
    if not e164:
        return ""
    return e164[:3] + "******" + e164[-4:]

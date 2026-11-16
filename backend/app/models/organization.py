from __future__ import annotations

from typing import Any

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamps, UUIDPk
from app.models.enums import OrgStatus

DEFAULT_ORG_SETTINGS: dict[str, Any] = {
    "working_hours": {"start": "09:30", "end": "18:30", "days": [0, 1, 2, 3, 4, 5]},
    "notifications": {"whatsapp_enabled": True, "email_enabled": True, "auto_deliver_on_approval": True},
    "reminders": {
        "frequency_hours": 48,
        "max_reminders": 3,
        "quiet_hours_start": "21:00",
        "quiet_hours_end": "09:00",
        "invoice_reminders_enabled": True,
        "document_reminders_enabled": True,
    },
    "invoice": {"prefix": "INV", "default_tax_rate": 18.0, "payment_terms_days": 15, "gstin": "", "footer": ""},
    "privacy": {"document_retention_days": 2920, "notice_version": "2026-01"},
}


class Organization(UUIDPk, Timestamps, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(20))
    address: Mapped[str | None] = mapped_column(Text)
    logo_storage_key: Mapped[str | None] = mapped_column(String(255))
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata")
    status: Mapped[str] = mapped_column(String(20), default=OrgStatus.ACTIVE)
    onboarding_step: Mapped[str] = mapped_column(String(40), default="FIRM_PROFILE")
    settings: Mapped[dict[str, Any]] = mapped_column(default=lambda: {})
    invoice_seq: Mapped[int] = mapped_column(Integer, default=0)

    def get_setting(self, section: str, key: str) -> Any:
        merged = {**DEFAULT_ORG_SETTINGS.get(section, {}), **(self.settings or {}).get(section, {})}
        return merged.get(key)

    def merged_settings(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for section, defaults in DEFAULT_ORG_SETTINGS.items():
            out[section] = {**defaults, **(self.settings or {}).get(section, {})}
        return out

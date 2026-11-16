from __future__ import annotations

import hashlib
import hmac
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class OrderResult:
    order_id: str
    amount_paise: int
    currency: str
    key_id: str  # public key for checkout (safe to expose)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class PaymentLinkResult:
    link_id: str
    short_url: str
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderPayment:
    payment_id: str
    order_id: str | None
    status: str  # created | authorized | captured | failed | refunded
    amount_paise: int
    currency: str
    method: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class WebhookPayload:
    event_id: str
    event: str
    payment: ProviderPayment | None
    notes: dict[str, Any] = field(default_factory=dict)


class PaymentProvider(ABC):
    name: str

    @abstractmethod
    def create_order(self, *, amount_paise: int, currency: str, receipt: str, notes: dict[str, str]) -> OrderResult: ...

    @abstractmethod
    def create_payment_link(
        self,
        *,
        amount_paise: int,
        currency: str,
        description: str,
        reference_id: str,
        customer: dict[str, str],
        notes: dict[str, str],
        callback_url: str,
    ) -> PaymentLinkResult: ...

    @abstractmethod
    def verify_payment(self, *, order_id: str, payment_id: str, signature: str) -> bool:
        """Verify checkout signature: HMAC_SHA256(order_id|payment_id, key_secret)."""

    @abstractmethod
    def process_webhook(self, body: bytes, signature: str | None) -> WebhookPayload:
        """Verify webhook signature and parse. Raises Unauthorized on bad signature."""

    @abstractmethod
    def get_payment_status(self, payment_id: str) -> ProviderPayment: ...

    @abstractmethod
    def get_order_payments(self, order_id: str) -> list[ProviderPayment]: ...


def hmac_hex(secret: str, msg: bytes) -> str:
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()

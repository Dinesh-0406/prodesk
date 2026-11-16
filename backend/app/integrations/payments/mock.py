"""Mock payment gateway with Razorpay-identical signature semantics.

State is kept in Redis so the API and workers agree. The mock "checkout" is driven by
``complete_checkout`` (dev-only endpoint), which plays the role of the gateway: it creates a
captured payment and returns a signature the backend must still verify.
"""

from __future__ import annotations

import hmac
import json
import uuid
from typing import Any

from app.core.errors import NotFound, Unauthorized
from app.core.redis import get_redis
from app.integrations.payments.base import (
    OrderResult,
    PaymentLinkResult,
    PaymentProvider,
    ProviderPayment,
    WebhookPayload,
    hmac_hex,
)

TTL = 7 * 86400


class MockPaymentProvider(PaymentProvider):
    name = "mock"

    def __init__(self, secret: str, frontend_url: str) -> None:
        self.secret = secret
        self.frontend_url = frontend_url.rstrip("/")

    def _save(self, kind: str, id_: str, data: dict[str, Any]) -> None:
        get_redis().setex(f"mockpay:{kind}:{id_}", TTL, json.dumps(data))

    def _load(self, kind: str, id_: str) -> dict[str, Any]:
        raw = get_redis().get(f"mockpay:{kind}:{id_}")
        if not raw:
            raise NotFound("Payment record not found")
        return json.loads(raw)  # type: ignore[no-any-return]

    def create_order(self, *, amount_paise: int, currency: str, receipt: str, notes: dict[str, str]) -> OrderResult:
        oid = f"order_mock{uuid.uuid4().hex[:14]}"
        self._save("order", oid, {"amount": amount_paise, "currency": currency, "notes": notes, "payments": []})
        return OrderResult(order_id=oid, amount_paise=amount_paise, currency=currency, key_id="rzp_test_mock")

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
    ) -> PaymentLinkResult:
        lid = f"plink_mock{uuid.uuid4().hex[:12]}"
        return PaymentLinkResult(link_id=lid, short_url=callback_url)

    def complete_checkout(self, order_id: str, *, succeed: bool = True) -> dict[str, str]:
        order = self._load("order", order_id)
        pid = f"pay_mock{uuid.uuid4().hex[:14]}"
        status = "captured" if succeed else "failed"
        self._save(
            "payment",
            pid,
            {"order_id": order_id, "status": status, "amount": order["amount"], "currency": order["currency"], "method": "upi"},
        )
        order["payments"].append(pid)
        self._save("order", order_id, order)
        return {
            "razorpay_order_id": order_id,
            "razorpay_payment_id": pid,
            "razorpay_signature": hmac_hex(self.secret, f"{order_id}|{pid}".encode()),
        }

    def verify_payment(self, *, order_id: str, payment_id: str, signature: str) -> bool:
        return hmac.compare_digest(hmac_hex(self.secret, f"{order_id}|{payment_id}".encode()), signature or "")

    def process_webhook(self, body: bytes, signature: str | None) -> WebhookPayload:
        if not signature or not hmac.compare_digest(hmac_hex(self.secret, body), signature):
            raise Unauthorized("Invalid webhook signature", code="INVALID_SIGNATURE")
        data = json.loads(body)
        entity = (data.get("payload", {}).get("payment") or {}).get("entity")
        payment = None
        if entity:
            payment = ProviderPayment(
                payment_id=entity["id"],
                order_id=entity.get("order_id"),
                status=entity["status"],
                amount_paise=int(entity["amount"]),
                currency=entity.get("currency", "INR"),
                method=entity.get("method"),
            )
        return WebhookPayload(event_id=data["id"], event=data["event"], payment=payment, notes=(entity or {}).get("notes") or {})

    def get_payment_status(self, payment_id: str) -> ProviderPayment:
        p = self._load("payment", payment_id)
        return ProviderPayment(
            payment_id=payment_id,
            order_id=p["order_id"],
            status=p["status"],
            amount_paise=int(p["amount"]),
            currency=p["currency"],
            method=p.get("method"),
        )

    def get_order_payments(self, order_id: str) -> list[ProviderPayment]:
        try:
            order = self._load("order", order_id)
        except NotFound:
            return []
        return [self.get_payment_status(pid) for pid in order.get("payments", [])]

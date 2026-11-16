"""Razorpay provider using the REST API directly (https://razorpay.com/docs/api/)."""

from __future__ import annotations

import hmac
import json
from typing import Any

import httpx

from app.core.errors import ProviderError, Unauthorized
from app.core.logging import get_logger
from app.integrations.payments.base import (
    OrderResult,
    PaymentLinkResult,
    PaymentProvider,
    ProviderPayment,
    WebhookPayload,
    hmac_hex,
)

log = get_logger("payments.razorpay")
API = "https://api.razorpay.com/v1"


def _to_payment(p: dict[str, Any]) -> ProviderPayment:
    return ProviderPayment(
        payment_id=p["id"],
        order_id=p.get("order_id"),
        status=p.get("status", "unknown"),
        amount_paise=int(p.get("amount", 0)),
        currency=p.get("currency", "INR"),
        method=p.get("method"),
        raw={k: p.get(k) for k in ("id", "status", "method", "amount", "captured")},
    )


class RazorpayProvider(PaymentProvider):
    name = "razorpay"

    def __init__(self, key_id: str, key_secret: str, webhook_secret: str) -> None:
        if not key_id or not key_secret:
            raise ProviderError("Razorpay is not configured", code="PAYMENTS_NOT_CONFIGURED")
        self.key_id = key_id
        self.key_secret = key_secret
        self.webhook_secret = webhook_secret
        self._client = httpx.Client(base_url=API, auth=(key_id, key_secret), timeout=15)

    def _req(self, method: str, path: str, **kw: Any) -> dict[str, Any]:
        try:
            resp = self._client.request(method, path, **kw)
        except httpx.HTTPError as e:
            raise ProviderError("Payment provider unreachable", code="PAYMENT_PROVIDER_UNAVAILABLE") from e
        if resp.status_code >= 300:
            log.warning("razorpay_error", extra={"http_status": resp.status_code, "path": path.split("/")[1]})
            raise ProviderError("Payment provider error", code="PAYMENT_PROVIDER_ERROR", details={"status": resp.status_code})
        return resp.json()  # type: ignore[no-any-return]

    def create_order(self, *, amount_paise: int, currency: str, receipt: str, notes: dict[str, str]) -> OrderResult:
        data = self._req("POST", "/orders", json={"amount": amount_paise, "currency": currency, "receipt": receipt[:40], "notes": notes})
        return OrderResult(
            order_id=data["id"],
            amount_paise=data["amount"],
            currency=data["currency"],
            key_id=self.key_id,
            raw={"id": data["id"], "status": data.get("status")},
        )

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
        data = self._req(
            "POST",
            "/payment_links",
            json={
                "amount": amount_paise,
                "currency": currency,
                "description": description[:2048],
                "reference_id": reference_id[:40],
                "customer": customer,
                "notes": notes,
                "notify": {"sms": False, "email": False},
                "callback_url": callback_url,
                "callback_method": "get",
            },
        )
        return PaymentLinkResult(link_id=data["id"], short_url=data["short_url"], raw={"id": data["id"]})

    def verify_payment(self, *, order_id: str, payment_id: str, signature: str) -> bool:
        expected = hmac_hex(self.key_secret, f"{order_id}|{payment_id}".encode())
        return hmac.compare_digest(expected, signature or "")

    def process_webhook(self, body: bytes, signature: str | None) -> WebhookPayload:
        if not self.webhook_secret or not signature or not hmac.compare_digest(hmac_hex(self.webhook_secret, body), signature):
            raise Unauthorized("Invalid webhook signature", code="INVALID_SIGNATURE")
        data = json.loads(body)
        entity = (data.get("payload", {}).get("payment") or {}).get("entity")
        return WebhookPayload(
            event_id=data.get("id") or data.get("event", "") + ":" + str(data.get("created_at")),
            event=data.get("event", ""),
            payment=_to_payment(entity) if entity else None,
            notes=(entity or {}).get("notes") or {},
        )

    def get_payment_status(self, payment_id: str) -> ProviderPayment:
        return _to_payment(self._req("GET", f"/payments/{payment_id}"))

    def get_order_payments(self, order_id: str) -> list[ProviderPayment]:
        data = self._req("GET", f"/orders/{order_id}/payments")
        return [_to_payment(p) for p in data.get("items", [])]

from __future__ import annotations

import json
from decimal import Decimal

from conftest import Firm

from app.integrations.payments.base import hmac_hex


def _invoice(api, firm: Firm, client_id: str, send: bool = True) -> dict:
    inv = api.post(
        "/api/v1/invoices",
        headers=firm.h,
        json={
            "client_id": client_id,
            "items": [
                {"description": "ITR filing", "unit_price": "3500", "tax_rate": "18"},
                {"description": "Expenses", "unit_price": "100.50", "tax_rate": "0", "quantity": "2"},
            ],
        },
    ).json()
    if send:
        inv = api.post(f"/api/v1/invoices/{inv['id']}/send", headers=firm.h).json()
    return inv


def test_invoice_totals_numbering_and_send(api, firm: Firm):
    c = firm.client()
    inv = _invoice(api, firm, c["id"], send=False)
    assert Decimal(inv["subtotal"]) == Decimal("3701.00")
    assert Decimal(inv["tax"]) == Decimal("630.00")
    assert Decimal(inv["total"]) == Decimal("4331.00") and inv["status"] == "DRAFT"
    inv2 = _invoice(api, firm, c["id"], send=False)
    assert inv["invoice_number"].endswith("/00001") and inv2["invoice_number"].endswith("/00002")
    sent = api.post(f"/api/v1/invoices/{inv['id']}/send", headers=firm.h).json()
    assert sent["status"] == "SENT"


def _checkout_and_pay(api, firm: Firm, ph: dict, invoice_id: str) -> tuple[dict, dict]:
    co = api.post(f"/api/v1/portal/invoices/{invoice_id}/checkout", headers=ph)
    assert co.status_code == 200, co.text
    sig = api.post("/api/v1/portal/payments/mock-complete", headers=ph, json={"order_id": co.json()["order_id"]}).json()
    return co.json(), sig


def test_payment_verified_server_side(api, firm: Firm):
    c = firm.client("Payer", "9877000001")
    inv = _invoice(api, firm, c["id"])
    ph = firm.portal_login(c["phone"])
    co, sig = _checkout_and_pay(api, firm, ph, inv["id"])
    assert co["amount_paise"] == 433100
    r = api.post("/api/v1/portal/payments/verify", headers=ph, json=sig)
    assert r.status_code == 200 and r.json()["status"] == "PAID"
    # replay of the same verification is idempotent (no double counting)
    r = api.post("/api/v1/portal/payments/verify", headers=ph, json=sig)
    assert r.status_code == 200 and Decimal(r.json()["amount_paid"]) == Decimal("4331.00")
    pays = api.get("/api/v1/payments", headers=firm.h).json()
    assert pays["total"] == 1 and pays["items"][0]["verified_via"] == "SIGNATURE"
    logs = api.get("/api/v1/audit-logs", headers=firm.h, params={"action": "PAYMENT_RECEIVED"}).json()
    assert logs["total"] == 1


def test_forged_payment_signature_rejected(api, firm: Firm):
    c = firm.client("Forger", "9877000002")
    inv = _invoice(api, firm, c["id"])
    ph = firm.portal_login(c["phone"])
    co = api.post(f"/api/v1/portal/invoices/{inv['id']}/checkout", headers=ph).json()
    forged = {
        "razorpay_order_id": co["order_id"],
        "razorpay_payment_id": "pay_fake123",
        "razorpay_signature": hmac_hex("wrong-secret", f"{co['order_id']}|pay_fake123".encode()),
    }
    r = api.post("/api/v1/portal/payments/verify", headers=ph, json=forged)
    assert r.status_code == 422 and r.json()["error"]["code"] == "INVALID_PAYMENT_SIGNATURE"
    # correct signature for a payment that was never captured → still rejected (provider check)
    valid_sig = hmac_hex("test-mock-pay-secret", f"{co['order_id']}|pay_fake123".encode())
    r = api.post("/api/v1/portal/payments/verify", headers=ph, json={**forged, "razorpay_signature": valid_sig})
    assert r.status_code == 404
    assert api.get(f"/api/v1/invoices/{inv['id']}", headers=firm.h).json()["status"] == "SENT"


def test_client_cannot_pay_or_verify_other_clients_invoice(api, firm: Firm):
    a = firm.client("Client A", "9877000003")
    b = firm.client("Client B", "9877000004")
    inv_b = _invoice(api, firm, b["id"])
    ph_a = firm.portal_login(a["phone"])
    assert api.post(f"/api/v1/portal/invoices/{inv_b['id']}/checkout", headers=ph_a).status_code == 404
    assert api.get(f"/api/v1/portal/invoices/{inv_b['id']}", headers=ph_a).status_code == 404
    ph_b = firm.portal_login(b["phone"])
    _co, sig = _checkout_and_pay(api, firm, ph_b, inv_b["id"])
    assert api.post("/api/v1/portal/payments/verify", headers=ph_a, json=sig).status_code == 404


def test_payment_webhook_signature_and_idempotency(api, firm: Firm):
    c = firm.client("Hook", "9877000005")
    inv = _invoice(api, firm, c["id"])
    ph = firm.portal_login(c["phone"])
    co, sig = _checkout_and_pay(api, firm, ph, inv["id"])
    event = {
        "id": "evt_test_1",
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": sig["razorpay_payment_id"],
                    "order_id": co["order_id"],
                    "status": "captured",
                    "amount": co["amount_paise"],
                    "currency": "INR",
                    "method": "upi",
                }
            }
        },
    }
    body = json.dumps(event).encode()
    assert api.post("/api/v1/webhooks/razorpay", content=body, headers={"X-Razorpay-Signature": "bad"}).status_code == 401
    good = {"X-Razorpay-Signature": hmac_hex("test-mock-pay-secret", body)}
    assert api.post("/api/v1/webhooks/razorpay", content=body, headers=good).json()["status"] == "ok"
    assert api.post("/api/v1/webhooks/razorpay", content=body, headers=good).json()["status"] == "duplicate"
    # browser callback afterwards must not double-record
    api.post("/api/v1/portal/payments/verify", headers=ph, json=sig)
    inv_after = api.get(f"/api/v1/invoices/{inv['id']}", headers=firm.h).json()
    assert inv_after["status"] == "PAID" and Decimal(inv_after["amount_paid"]) == Decimal(inv["total"])
    assert api.get("/api/v1/payments", headers=firm.h).json()["total"] == 1


def test_manual_partial_payment(api, firm: Firm):
    c = firm.client()
    inv = _invoice(api, firm, c["id"])
    r = api.post(f"/api/v1/invoices/{inv['id']}/payments", headers=firm.h, json={"amount": "1000", "reference": "NEFT-001"})
    assert r.status_code == 201
    assert api.get(f"/api/v1/invoices/{inv['id']}", headers=firm.h).json()["status"] == "PARTIALLY_PAID"
    assert (
        api.post(f"/api/v1/invoices/{inv['id']}/payments", headers=firm.h, json={"amount": "1000", "reference": "NEFT-001"}).status_code
        == 422
    )  # duplicate reference
    assert (
        api.post(f"/api/v1/invoices/{inv['id']}/payments", headers=firm.h, json={"amount": "99999", "reference": "NEFT-002"}).status_code
        == 422
    )  # exceeds balance
    assert api.post(f"/api/v1/invoices/{inv['id']}/cancel", headers=firm.h).status_code == 422


def test_reconciliation_catches_lost_callbacks(api, firm: Firm, db):
    from datetime import timedelta

    from app.models import PaymentAttempt
    from app.services.payments import reconcile_pending

    c = firm.client("Recon", "9877000006")
    inv = _invoice(api, firm, c["id"])
    ph = firm.portal_login(c["phone"])
    _checkout_and_pay(api, firm, ph, inv["id"])  # paid at gateway, but no verify / webhook reached us
    a = db.query(PaymentAttempt).one()
    a.created_at = a.created_at - timedelta(minutes=30)
    db.commit()
    assert reconcile_pending(db) == 1
    assert api.get(f"/api/v1/invoices/{inv['id']}", headers=firm.h).json()["status"] == "PAID"

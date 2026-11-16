from __future__ import annotations

from datetime import timedelta

from conftest import Firm, last_outbound, make_pdf, send_webhook, status_webhook
from sqlalchemy import func, select

from app.models import Message, MessageTemplate, WebhookEvent


def test_webhook_verification(api):
    ok = api.get(
        "/api/v1/webhooks/whatsapp", params={"hub.mode": "subscribe", "hub.verify_token": "test-verify-token", "hub.challenge": "12345"}
    )
    assert ok.status_code == 200 and ok.text == "12345"
    bad = api.get("/api/v1/webhooks/whatsapp", params={"hub.mode": "subscribe", "hub.verify_token": "nope", "hub.challenge": "1"})
    assert bad.status_code == 403


def test_fake_webhook_rejected(api, firm: Firm, db):
    c = firm.client("Fake Target", "9876700001")
    r = firm.inbound(c["phone"], "hi", signed=False)
    assert r.status_code == 401
    import json

    raw = json.dumps({"object": "whatsapp_business_account", "entry": []}).encode()
    r = api.post("/api/v1/webhooks/whatsapp", content=raw, headers={"X-Hub-Signature-256": "sha256=" + "0" * 64})
    assert r.status_code == 401
    assert db.execute(select(func.count()).select_from(WebhookEvent)).scalar_one() == 0


def test_inbound_message_and_bot_reply(api, firm: Firm, db):
    c = firm.client("Rahul", "9876700002")
    r = firm.inbound(c["phone"], "Mera payment kitna pending hai?")
    assert r.status_code == 200 and r.json()["accepted"] == 1
    reply = last_outbound(db, firm.org_id, "pending payments")
    assert reply is not None and reply.sender == "BOT" and reply.status == "SENT"
    convs = api.get("/api/v1/conversations", headers=firm.h).json()["items"]
    assert convs[0]["client"]["id"] == c["id"] and convs[0]["service_window_open"] is True


def test_duplicate_webhook_is_idempotent(api, firm: Firm, db):
    c = firm.client("Dup", "9876700003")
    for _ in range(3):
        r = firm.inbound(c["phone"], "Invoice bhejo", msg_id="wamid.DUPLICATE123")
        assert r.status_code == 200
    inbound = db.execute(select(func.count()).select_from(Message).where(Message.provider_message_id == "wamid.DUPLICATE123")).scalar_one()
    assert inbound == 1
    bot_replies = db.execute(select(func.count()).select_from(Message).where(Message.sender == "BOT")).scalar_one()
    assert bot_replies == 1  # no duplicate actions


def test_unknown_number_gets_generic_reply(api, firm: Firm, db):
    r = send_webhook(api, firm.phone_number_id, "919999999999", "Mera ITR status kya hai?")
    assert r.status_code == 200
    reply = last_outbound(db, firm.org_id)
    assert "not registered" in reply.body
    assert "ITR" not in reply.body


def test_status_webhooks_update_delivery(api, firm: Firm, db):
    c = firm.client("Delivery", "9876700004")
    d = firm.upload(c["id"], document_type="BALANCE_SHEET").json()
    api.post(f"/api/v1/documents/{d['id']}/approve", headers=firm.h)
    msg = last_outbound(db, firm.org_id, "Balance Sheet")
    for s in ("delivered", "read", "delivered"):  # out-of-order status must not regress
        assert status_webhook(api, firm.phone_number_id, msg.provider_message_id, s).status_code == 200
    db.refresh(msg)
    assert msg.status == "READ" and msg.read_at and msg.delivered_at
    dl = api.get(f"/api/v1/documents/{d['id']}", headers=firm.h).json()["deliveries"][0]
    assert dl["status"] == "READ" and dl["delivered_at"] and dl["read_at"]


def test_opt_out_blocks_messages(api, firm: Firm, db):
    c = firm.client("Opt", "9876700005")
    firm.inbound(c["phone"], "STOP")
    cl = api.get(f"/api/v1/clients/{c['id']}", headers=firm.h).json()
    assert cl["whatsapp_opt_out_at"] is not None
    d = firm.upload(c["id"]).json()
    api.post(f"/api/v1/documents/{d['id']}/approve", headers=firm.h)
    detail = api.get(f"/api/v1/documents/{d['id']}", headers=firm.h).json()
    assert detail["status"] == "APPROVED"  # not delivered
    assert detail["deliveries"][0]["status"] == "FAILED" and "OPTED_OUT" in detail["deliveries"][0]["error"]
    firm.inbound(c["phone"], "START")
    assert api.get(f"/api/v1/clients/{c['id']}", headers=firm.h).json()["whatsapp_opt_in"] is True


def test_template_not_approved_handled_gracefully(api, firm: Firm, db):
    db.execute(
        MessageTemplate.__table__.update()
        .where(MessageTemplate.organization_id == firm.org_id, MessageTemplate.key == "DOCUMENT_READY")
        .values(status="PENDING")
    )
    db.commit()
    c = firm.client("Tpl", "9876700006")
    d = firm.upload(c["id"]).json()
    assert api.post(f"/api/v1/documents/{d['id']}/approve", headers=firm.h).status_code == 200
    dl = api.get(f"/api/v1/documents/{d['id']}", headers=firm.h).json()["deliveries"][0]
    assert dl["status"] == "FAILED" and "TEMPLATE_NOT_APPROVED" in dl["error"]
    notes = api.get("/api/v1/notifications", headers=firm.h).json()
    assert any(n["type"] == "DELIVERY_FAILED" for n in notes)


def test_template_rejected_by_provider(api, firm: Firm, db):
    db.execute(
        MessageTemplate.__table__.update()
        .where(MessageTemplate.organization_id == firm.org_id, MessageTemplate.key == "INVOICE_CREATED")
        .values(name="rejected_invoice")
    )
    db.commit()
    c = firm.client("Rej", "9876700007")
    inv = api.post(
        "/api/v1/invoices", headers=firm.h, json={"client_id": c["id"], "items": [{"description": "Fee", "unit_price": "100"}]}
    ).json()
    assert api.post(f"/api/v1/invoices/{inv['id']}/send", headers=firm.h).status_code == 200
    db.expire_all()
    tpl = db.execute(
        select(MessageTemplate).where(MessageTemplate.organization_id == firm.org_id, MessageTemplate.key == "INVOICE_CREATED")
    ).scalar_one()
    assert tpl.status == "REJECTED" and tpl.last_error
    msg = last_outbound(db, firm.org_id, "invoice")
    assert msg.status == "FAILED" and msg.error_code == "132015"


def test_freeform_outside_service_window_blocked(api, firm: Firm, db):
    from app.models import WhatsAppContact

    c = firm.client("Window", "9876700008")
    firm.inbound(c["phone"], "hello")
    conv = api.get("/api/v1/conversations", headers=firm.h).json()["items"][0]
    assert api.post(f"/api/v1/conversations/{conv['id']}/messages", headers=firm.h, json={"body": "Hi!"}).status_code == 201
    contact = db.execute(select(WhatsAppContact)).scalars().first()
    contact.last_inbound_at = contact.last_inbound_at - timedelta(hours=25)
    db.commit()
    r = api.post(f"/api/v1/conversations/{conv['id']}/messages", headers=firm.h, json={"body": "Hi again"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "OUTSIDE_SERVICE_WINDOW"


def test_human_handover_suppresses_ai(api, firm: Firm, db):
    c = firm.client("Handover", "9876700009")
    firm.inbound(c["phone"], "CA se baat karni hai")
    conv = api.get("/api/v1/conversations", headers=firm.h).json()["items"][0]
    assert conv["handover_state"] == "HUMAN_REQUESTED"
    assert any(n["type"] == "HUMAN_HANDOFF" for n in api.get("/api/v1/notifications", headers=firm.h).json())
    bot_before = db.execute(select(func.count()).select_from(Message).where(Message.sender == "BOT")).scalar_one()
    firm.inbound(c["phone"], "Mera ITR status kya hai?")
    bot_after = db.execute(select(func.count()).select_from(Message).where(Message.sender == "BOT")).scalar_one()
    assert bot_after == bot_before  # AI did not reply in human mode
    r = api.post(f"/api/v1/conversations/{conv['id']}/handover", headers=firm.h, json={"action": "take"})
    assert r.json()["handover_state"] == "AGENT_ASSIGNED"
    r = api.post(f"/api/v1/conversations/{conv['id']}/messages", headers=firm.h, json={"body": "Hi, this is your CA."})
    assert r.status_code == 201 and r.json()["sender"] == "AGENT"
    assert api.get(f"/api/v1/conversations/{conv['id']}", headers=firm.h).json()["handover_state"] == "HUMAN_ACTIVE"
    api.post(f"/api/v1/conversations/{conv['id']}/handover", headers=firm.h, json={"action": "resume_bot"})
    firm.inbound(c["phone"], "Mera ITR status kya hai?")
    bot_final = db.execute(select(func.count()).select_from(Message).where(Message.sender == "BOT")).scalar_one()
    assert bot_final == bot_after + 1


def test_inbound_document_attaches_to_request(api, firm: Firm, db):
    c = firm.client("Uploader", "9876700010")
    req = api.post(
        "/api/v1/document-requests",
        headers=firm.h,
        json={"client_id": c["id"], "title": "GST docs", "items": [{"name": "Bank Statement", "document_type": "BANK_STATEMENT"}]},
    ).json()
    r = firm.inbound(c["phone"], media=(make_pdf("statement"), "application/pdf", "statement.pdf"))
    assert r.status_code == 200
    req = api.get(f"/api/v1/document-requests/{req['id']}", headers=firm.h).json()
    assert req["status"] == "COMPLETE" and req["items"][0]["document_id"]
    doc = api.get(f"/api/v1/documents/{req['items'][0]['document_id']}", headers=firm.h).json()
    assert doc["source"] == "WHATSAPP" and doc["client_id"] == c["id"]
    assert "All requested documents" in last_outbound(db, firm.org_id).body
    # malicious attachment is refused
    firm.inbound(c["phone"], media=(b"MZ\x90\x00evil", "application/pdf", "evil.pdf"))
    assert "couldn't accept" in last_outbound(db, firm.org_id).body


def test_whatsapp_settings_never_expose_tokens(api, firm: Firm):
    r = api.put(
        "/api/v1/whatsapp/account",
        headers=firm.h,
        json={
            "provider": "mock",
            "phone_number_id": firm.phone_number_id,
            "access_token": "EAAG-super-secret-token-1234",
            "app_secret": "app-secret-value",
        },
    )
    body = r.json()
    assert "EAAG-super-secret-token-1234" not in r.text and "app-secret-value" not in r.text
    assert body["access_token_set"] is True and body["access_token_hint"].endswith("1234")
    logs = api.get("/api/v1/audit-logs", headers=firm.h, params={"action": "WHATSAPP_CONFIGURED"}).text
    assert "super-secret" not in logs


def test_phone_number_id_cannot_be_hijacked(api, firm: Firm, other_firm: Firm):
    r = api.put("/api/v1/whatsapp/account", headers=other_firm.h, json={"provider": "mock", "phone_number_id": firm.phone_number_id})
    assert r.status_code == 409

"""WhatsApp document desk: identify by name or number, pick from a list, receive the file."""

from __future__ import annotations

import json

import pytest
from conftest import Firm, last_outbound, make_pdf
from sqlalchemy import select

from app.integrations.whatsapp.base import sign_meta_payload
from app.integrations.whatsapp.mock import OUTBOX
from app.models import AuditLog, DocumentDelivery
from app.services.assistant.document_bot import parse_claim
from app.services.whatsapp_webhook import build_simulated_payload

STRANGER = "919000000001"


def _post(api, raw: bytes):
    headers = {"Content-Type": "application/json", "X-Hub-Signature-256": sign_meta_payload("test-app-secret", raw)}
    r = api.post("/api/v1/webhooks/whatsapp", content=raw, headers=headers)
    assert r.status_code == 200, r.text
    return r


def say(api, firm: Firm, wa_id: str, text: str):
    return _post(api, build_simulated_payload(firm.phone_number_id, wa_id, text=text, profile_name="X", media=None, caption=None))


def pick(api, firm: Firm, wa_id: str, row_id: str, title: str = "Balance Sheet"):
    data = json.loads(build_simulated_payload(firm.phone_number_id, wa_id, text="x", profile_name="X", media=None, caption=None))
    m = data["entry"][0]["changes"][0]["value"]["messages"][0]
    m.pop("text", None)
    m.update(type="interactive", interactive={"type": "list_reply", "list_reply": {"id": row_id, "title": title}})
    return _post(api, json.dumps(data).encode())


def approved_doc(api, firm: Firm, client_id: str, doc_type: str, fy: str = "2025-26", content: bytes | None = None) -> dict:
    d = firm.upload(client_id, name=f"{doc_type}_{fy}.pdf", document_type=doc_type, fy=fy, content=content).json()
    assert api.post(f"/api/v1/documents/{d['id']}/approve", headers=firm.h, json={"deliver": False}).status_code == 200
    return d


def sent(kind: str, to: str | None = None) -> list[dict]:
    return [m for m in OUTBOX.messages if m["type"] == kind and (to is None or m["to"] == to)]


def otp_sent_to(wa_id: str) -> str | None:
    codes = [m["body_params"][0] for m in sent("template", wa_id) if m["template"] == "prodesk_otp"]
    return codes[-1] if codes else None


@pytest.mark.parametrize(
    ("text", "kind", "value"),
    [
        ("I am Abhishek Sahu", "name", "abhishek sahu"),
        ("Hi, I'm Mr. Abhishek Sahu.", "name", "abhishek sahu"),
        ("my name is abhishek sahu", "name", "abhishek sahu"),
        ("Main Abhishek Sahu hoon", "name", "abhishek sahu"),
        ("Mera naam Abhishek Sahu hai", "name", "abhishek sahu"),
        ("9876543210", "phone", "+919876543210"),
        ("+91 98765 43210", "phone", "+919876543210"),
        ("My number is 98765-43210", "phone", "+919876543210"),
    ],
)
def test_parse_claim(text, kind, value):
    c = parse_claim(text)
    assert c is not None and (c.kind, c.value) == (kind, value)


@pytest.mark.parametrize("text", ["Mera ITR status kya hai?", "send balance sheet", "123456", "I am", "hello"])
def test_parse_claim_ignores_other_messages(text):
    assert parse_claim(text) is None


def test_registered_number_lists_documents_and_sends_selected_file(api, firm: Firm, db):
    c = firm.client("Abhishek Sahu", "9876711111")
    wa = "919876711111"
    content = make_pdf("Balance Sheet FY 2025-26")
    bs = approved_doc(api, firm, c["id"], "BALANCE_SHEET", content=content)
    approved_doc(api, firm, c["id"], "PROFIT_LOSS")
    firm.upload(c["id"], document_type="GST_RETURN")  # not approved → never offered
    OUTBOX.clear()

    say(api, firm, wa, "I am Abhishek Sahu")
    menus = sent("interactive_list", wa)
    assert len(menus) == 1 and "Abhishek Sahu" in menus[0]["body"]
    titles = {r["title"] for r in menus[0]["rows"]}
    assert titles == {"Balance Sheet", "Profit & Loss Statement"}
    row = next(r for r in menus[0]["rows"] if r["title"] == "Balance Sheet")
    assert row["id"] == f"doc:{bs['id']}" and "FY 2025-26" in row["description"]

    pick(api, firm, wa, row["id"])
    files = sent("document", wa)
    assert len(files) == 1 and files[0]["file_name"] == "BALANCE_SHEET_2025-26.pdf" and "Balance Sheet" in files[0]["caption"]
    assert api.get(files[0]["link"].replace("http://testserver", "")).content == content
    db.expire_all()
    d = db.execute(select(DocumentDelivery).where(DocumentDelivery.document_id == bs["id"])).scalars().one()
    assert d.channel == "WHATSAPP_FILE" and d.status == "SENT" and d.message_id is not None
    assert api.get(f"/api/v1/documents/{bs['id']}", headers=firm.h).json()["status"] == "DELIVERED"
    assert db.execute(select(AuditLog).where(AuditLog.resource_id == bs["id"], AuditLog.action == "DOCUMENT_DELIVERY_CREATED")).first()


def test_documents_keyword_and_named_request(api, firm: Firm, db):
    c = firm.client("Keyword Client", "9876711112")
    wa = "919876711112"
    approved_doc(api, firm, c["id"], "BALANCE_SHEET")
    OUTBOX.clear()
    say(api, firm, wa, "Documents")
    assert len(sent("interactive_list", wa)) == 1
    say(api, firm, wa, "Please send my balance sheet")
    assert len(sent("document", wa)) == 1


def test_other_number_must_verify_with_otp_sent_to_registered_number(api, firm: Firm, db):
    c = firm.client("Abhishek Sahu", "9876722222")
    registered = "919876722222"
    bs = approved_doc(api, firm, c["id"], "BALANCE_SHEET")
    OUTBOX.clear()

    say(api, firm, STRANGER, "hello")
    assert "registered name" in last_outbound(db, firm.org_id).body

    say(api, firm, STRANGER, "I am Abhishek Sahu")
    assert last_outbound(db, firm.org_id, "6-digit verification code") is not None
    code = otp_sent_to(registered)
    assert code and otp_sent_to(STRANGER) is None  # the code goes to the registered number only
    assert not sent("interactive_list") and not sent("document")

    # Nothing is shared before verification, even with a forged list reply
    pick(api, firm, STRANGER, f"doc:{bs['id']}")
    assert not sent("document")

    wrong = "000000" if code != "000000" else "111111"
    say(api, firm, STRANGER, wrong)
    assert "not correct" in last_outbound(db, firm.org_id).body
    say(api, firm, STRANGER, f"{code[:3]} {code[3:]}")
    menu = sent("interactive_list", STRANGER)
    assert len(menu) == 1 and menu[0]["rows"][0]["id"] == f"doc:{bs['id']}"
    pick(api, firm, STRANGER, f"doc:{bs['id']}")
    assert len(sent("document", STRANGER)) == 1
    db.expire_all()
    assert db.execute(select(AuditLog).where(AuditLog.client_id == c["id"], AuditLog.action == "WHATSAPP_IDENTITY_VERIFIED")).first()

    # The code is single-use
    say(api, firm, STRANGER, code)
    assert len(sent("interactive_list", STRANGER)) == 1


def test_unknown_or_ambiguous_names_get_the_same_reply_and_no_code(api, firm: Firm, db):
    firm.client("Ravi Kumar", "9876733331")
    firm.client("Ravi Kumar", "9876733332")
    OUTBOX.clear()
    say(api, firm, STRANGER, "I am Nobody Real")
    unknown = last_outbound(db, firm.org_id).body
    say(api, firm, STRANGER, "I am Ravi Kumar")
    ambiguous = last_outbound(db, firm.org_id).body
    assert unknown == ambiguous and "If that name is registered" in unknown
    assert not [m for m in sent("template") if m["template"] == "prodesk_otp"]


def test_fuzzy_name_and_mobile_number_claims(api, firm: Firm, db):
    firm.client("Abhishek Sahu", "9876744441")
    OUTBOX.clear()
    say(api, firm, STRANGER, "I am Abhishek Sahoo")
    assert otp_sent_to("919876744441")
    firm.client("Priya Nair", "9876744442")
    say(api, firm, "919000000002", "My number is 98767 44442")
    assert otp_sent_to("919876744442")


def test_verified_chat_cannot_fetch_another_clients_document(api, firm: Firm, db):
    a = firm.client("Client Alpha", "9876755551")
    b = firm.client("Client Beta", "9876755552")
    approved_doc(api, firm, a["id"], "BALANCE_SHEET")
    b_doc = approved_doc(api, firm, b["id"], "BALANCE_SHEET")
    OUTBOX.clear()
    say(api, firm, "919876755551", "documents")
    pick(api, firm, "919876755551", f"doc:{b_doc['id']}")
    assert not sent("document")
    assert "no longer available" in last_outbound(db, firm.org_id).body


def test_chat_otp_does_not_interfere_with_portal_login(api, firm: Firm, db):
    c = firm.client("Portal User", "9876766661")
    say(api, firm, STRANGER, "I am Portal User")
    assert otp_sent_to("919876766661")
    firm.portal_login(c["phone"])  # portal OTP works independently

from __future__ import annotations

import uuid

import pytest
from conftest import Firm

from app.core.context import client_principal
from app.core.errors import Forbidden
from app.integrations.ai.base import ClientIntentName, StaffQueryName
from app.integrations.ai.mock import MockAIProvider
from app.services.assistant import tools


@pytest.mark.parametrize(
    "text,intent",
    [
        ("Mera ITR status kya hai?", ClientIntentName.GET_ITR_STATUS),
        ("Mujhe pichle saal ki balance sheet bhejo.", ClientIntentName.GET_DOCUMENT),
        ("Mere kaunse documents pending hain?", ClientIntentName.GET_PENDING_DOCUMENTS),
        ("Mera GST status kya hai?", ClientIntentName.GET_TASK_STATUS),
        ("Invoice bhejo.", ClientIntentName.GET_INVOICE),
        ("Mera payment kitna pending hai?", ClientIntentName.GET_PAYMENT_STATUS),
        ("Document upload karna hai.", ClientIntentName.UPLOAD_DOCUMENT),
        ("CA se baat karni hai.", ClientIntentName.HUMAN_HANDOFF),
        ("Human chahiye", ClientIntentName.HUMAN_HANDOFF),
        ("Agent se connect karo", ClientIntentName.HUMAN_HANDOFF),
        ("I want an appointment tomorrow", ClientIntentName.APPOINTMENT_REQUEST),
        ("asdf qwer", ClientIntentName.UNKNOWN),
    ],
)
def test_intent_classification(text, intent):
    assert MockAIProvider().classify_client_message(text).intent == intent


def test_entity_extraction():
    ai = MockAIProvider()
    i = ai.classify_client_message("Mujhe pichle saal ki balance sheet bhejo")
    assert i.document_type == "BALANCE_SHEET" and i.relative_year == -1
    i = ai.classify_client_message("send ITR acknowledgement for 2024-25")
    assert i.document_type == "ITR_ACKNOWLEDGEMENT" and i.financial_year == "2024-25"


def test_fy_helpers():
    from datetime import date

    assert tools.current_financial_year(date(2026, 11, 16)) == "2026-27"
    assert tools.current_financial_year(date(2027, 2, 1)) == "2026-27"
    assert tools.shift_fy("2026-27", -1) == "2025-26"


def test_tools_enforce_client_ownership(api, firm: Firm, other_firm: Firm, db):
    a = firm.client("Client A", "9870000001")
    b = firm.client("Client B", "9870000002")
    for c in (a, b):
        d = firm.upload(c["id"], document_type="BALANCE_SHEET").json()
        api.post(f"/api/v1/documents/{d['id']}/approve", headers=firm.h, json={"deliver": False})
    ctx_a = tools.ToolContext(principal=client_principal(uuid.UUID(firm.org_id), uuid.UUID(a["id"])))
    docs = tools.list_client_documents(db, ctx_a)
    assert len(docs) == 1 and str(docs[0].client_id) == a["id"]
    got = tools.get_document(db, ctx_a, document_type="BALANCE_SHEET")
    assert got is not None and str(got.client_id) == a["id"]
    # A principal claiming client B but in another org sees nothing
    ctx_wrong_org = tools.ToolContext(principal=client_principal(uuid.UUID(other_firm.org_id), uuid.UUID(b["id"])))
    assert tools.list_client_documents(db, ctx_wrong_org) == []
    assert tools.get_pending_documents(db, ctx_wrong_org) == []
    # Clients cannot create document requests through AI tools
    with pytest.raises(Forbidden):
        tools.create_document_request(db, ctx_a, title="x", items=["y"])


def test_unapproved_documents_never_offered_by_ai(api, firm: Firm, db):
    c = firm.client("Draft", "9870000003")
    firm.upload(c["id"], document_type="BALANCE_SHEET")  # not approved
    ctx = tools.ToolContext(principal=client_principal(uuid.UUID(firm.org_id), uuid.UUID(c["id"])))
    assert tools.get_document(db, ctx, document_type="BALANCE_SHEET") is None


def test_ai_never_claims_filed_without_backend_data(api, firm: Firm, db):
    from conftest import last_outbound

    c = firm.client("ITR Client", "9870000004")
    t = api.post(
        "/api/v1/tasks",
        headers=firm.h,
        json={"client_id": c["id"], "title": "ITR FY 2025-26", "service_type": "ITR", "status": "WORK_IN_PROGRESS"},
    ).json()
    firm.inbound(c["phone"], "Mera ITR status kya hai?")
    body = last_outbound(db, firm.org_id).body
    assert "Work in progress" in body and "filed" not in body.lower()
    api.patch(f"/api/v1/tasks/{t['id']}", headers=firm.h, json={"status": "FILED", "filing_reference": "ACK999"})
    firm.inbound(c["phone"], "Mera ITR status kya hai?")
    body = last_outbound(db, firm.org_id).body
    assert "Marked as filed" in body and "ACK999" in body


def test_advice_questions_are_routed_to_ca(api, firm: Firm, db):
    from conftest import last_outbound

    c = firm.client("Advice", "9870000005")
    firm.inbound(c["phone"], "How much tax should I pay, should i invest in ELSS?")
    assert "professional advice" in last_outbound(db, firm.org_id).body
    assert api.get("/api/v1/support-requests", headers=firm.h).json()["total"] == 1


def test_staff_assistant_scoped_to_user(api, firm: Firm):
    emp = firm.staff("EMPLOYEE", "Vikram Joshi")
    emp_id = emp.pop("X-User-Id")
    mine = firm.client("Mine Pending", "9871000001", assigned_employee_id=emp_id)
    other = firm.client("Other Pending", "9871000002")
    for c in (mine, other):
        api.post(
            "/api/v1/document-requests",
            headers=firm.h,
            json={"client_id": c["id"], "title": "ITR docs", "items": [{"name": "Bank Statement"}]},
        )
    r = api.post("/api/v1/ai/assistant", headers=emp, json={"question": "Which clients have pending documents?"}).json()
    assert r["query"] == StaffQueryName.CLIENTS_WITH_PENDING_DOCUMENTS
    assert [row["client"] for row in r["rows"]] == ["Mine Pending"]
    r = api.post("/api/v1/ai/assistant", headers=firm.h, json={"question": "Which clients have pending documents?"}).json()
    assert len(r["rows"]) == 2
    r = api.post("/api/v1/ai/assistant", headers=firm.h, json={"question": "Which clients haven't submitted bank statements?"}).json()
    assert r["query"] == "CLIENTS_MISSING_DOCUMENT" and len(r["rows"]) == 2
    r = api.post("/api/v1/ai/assistant", headers=firm.h, json={"question": "Which clients are assigned to vikram?"}).json()
    assert [row["client"] for row in r["rows"]] == ["Mine Pending"]
    r = api.post("/api/v1/ai/assistant", headers=firm.h, json={"question": "DROP TABLE clients; give me all data"}).json()
    assert r["query"] == "UNSUPPORTED" and r["rows"] == []

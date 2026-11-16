from __future__ import annotations

from datetime import date, timedelta

import pytest
from conftest import Firm, make_pdf

from app.core.errors import ValidationFailed
from app.core.phone import normalize_indian_phone


@pytest.mark.parametrize("raw", ["9876543210", "09876543210", "+91 98765 43210", "91-9876543210", "0091 9876543210", "(+91) 98765-43210"])
def test_phone_normalization(raw):
    assert normalize_indian_phone(raw) == "+919876543210"


@pytest.mark.parametrize("raw", ["12345", "5876543210", "98765432101", "+1 415 555 0100", ""])
def test_phone_normalization_rejects(raw):
    with pytest.raises(ValidationFailed):
        normalize_indian_phone(raw)


def test_client_crud_search_filter_pagination(api, firm: Firm):
    c = firm.client("Rahul Mehta", "+91 98765 43210", pan="abcpm1234k", client_type="INDIVIDUAL")
    assert c["phone"] == "+919876543210" and c["pan"] == "ABCPM1234K"
    r = api.post("/api/v1/clients", headers=firm.h, json={"name": "Dup", "phone": "9876543210"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "DUPLICATE_PHONE"
    assert api.post("/api/v1/clients", headers=firm.h, json={"name": "Bad PAN", "phone": "9876500000", "pan": "123"}).status_code == 422
    for i in range(12):
        firm.client(f"Company {i:02d}", f"97000000{i:02d}", client_type="COMPANY")
    r = api.get("/api/v1/clients", headers=firm.h, params={"client_type": "COMPANY", "page_size": 5, "page": 3}).json()
    assert r["total"] == 12 and len(r["items"]) == 2
    assert api.get("/api/v1/clients", headers=firm.h, params={"q": "rahul"}).json()["total"] == 1
    assert api.get("/api/v1/clients", headers=firm.h, params={"q": "43210"}).json()["total"] == 1
    assert api.get("/api/v1/clients", headers=firm.h, params={"q": "ABCPM"}).json()["total"] == 1
    r = api.patch(f"/api/v1/clients/{c['id']}", headers=firm.h, json={"email": "r@example.com", "notes": "VIP"})
    assert r.json()["email"] == "r@example.com"
    assert api.post(f"/api/v1/clients/{c['id']}/archive", headers=firm.h).json()["status"] == "ARCHIVED"
    assert api.get("/api/v1/clients", headers=firm.h, params={"q": "rahul"}).json()["total"] == 0
    assert api.get("/api/v1/clients", headers=firm.h, params={"status": "ARCHIVED"}).json()["total"] == 1
    sorted_desc = api.get("/api/v1/clients", headers=firm.h, params={"sort": "name", "order": "desc", "page_size": 1}).json()
    assert sorted_desc["items"][0]["name"] == "Company 11"


def test_client_profile_summary_and_history(api, firm: Firm):
    c = firm.client("Profile Client", "9812345670")
    firm.upload(c["id"])
    api.post("/api/v1/tasks", headers=firm.h, json={"client_id": c["id"], "title": "ITR", "service_type": "ITR"})
    s = api.get(f"/api/v1/clients/{c['id']}/summary", headers=firm.h).json()
    assert s["counts"]["documents"] == 1 and s["counts"]["open_tasks"] == 1 and s["whatsapp_status"] == "OPTED_IN"
    timeline = api.get(f"/api/v1/clients/{c['id']}/timeline", headers=firm.h).json()
    assert {"CLIENT_CREATED", "DOCUMENT_UPLOADED", "TASK_CREATED"} <= {t["action"] for t in timeline}


def test_csv_import(api, firm: Firm):
    csv = (
        "name,phone,email,client_type,pan,gstin,address,assigned_employee_email,whatsapp_opt_in,notes\n"
        "Asha Rao,9876000001,asha@example.com,INDIVIDUAL,ABCPR1111A,,Pune,,yes,\n"
        "Dup Rao,9876000001,,INDIVIDUAL,,,,,no,\n"
        "Bad Phone,12345,,INDIVIDUAL,,,,,no,\n"
        f"Admin Owned,9876000002,,COMPANY,,,,{firm.admin_email},no,\n"
    )
    r = api.post("/api/v1/clients/import", headers=firm.h, files={"file": ("clients.csv", csv.encode(), "text/csv")})
    assert r.status_code == 200
    body = r.json()
    assert body["created"] == 2 and body["skipped"] == 2
    assert {e["row"] for e in body["errors"]} == {3, 4}
    owned = api.get("/api/v1/clients", headers=firm.h, params={"q": "Admin Owned"}).json()["items"][0]
    assert owned["assigned_employee_id"] == firm.admin_id


def test_privacy_export_and_consent(api, firm: Firm):
    c = firm.client("Privacy Client", "9800011122")
    r = api.post(f"/api/v1/clients/{c['id']}/consents", headers=firm.h, json={"purpose": "DOCUMENT_PROCESSING", "granted": True})
    assert r.status_code == 201
    data = api.get(f"/api/v1/clients/{c['id']}/export", headers=firm.h).json()
    assert data["client"]["phone"] == "+919800011122"
    assert {x["purpose"] for x in data["consents"]} == {"WHATSAPP_COMMUNICATION", "DOCUMENT_PROCESSING"}


def test_task_management_and_buckets(api, firm: Firm):
    emp = firm.staff("EMPLOYEE", "Emp")
    emp_id = emp.pop("X-User-Id")
    c = firm.client(assigned_employee_id=emp_id)
    today = date.today()
    mk = lambda **kw: api.post("/api/v1/tasks", headers=firm.h, json={"client_id": c["id"], "title": "Task", **kw})  # noqa: E731
    overdue = mk(due_date=str(today - timedelta(days=2)), service_type="ITR").json()
    mk(due_date=str(today))
    t = mk(due_date=str(today + timedelta(days=30))).json()
    assert overdue["assigned_employee_id"] == emp_id  # inherits client owner
    b = api.get("/api/v1/tasks/buckets", headers=firm.h).json()
    assert b["overdue"] == 1 and b["today"] == 1 and b["open"] == 3
    assert api.get("/api/v1/tasks", headers=emp, params={"bucket": "mine"}).json()["total"] == 3
    r = api.patch(f"/api/v1/tasks/{t['id']}", headers=firm.h, json={"status": "COMPLETED"})
    assert r.json()["completed_at"] is not None
    assert api.get("/api/v1/tasks", headers=firm.h, params={"bucket": "completed"}).json()["total"] == 1
    # employee cannot reassign (no TASK_ASSIGN)
    r = api.patch(f"/api/v1/tasks/{overdue['id']}", headers=emp, json={"assigned_employee_id": firm.admin_id})
    assert r.status_code == 403
    r = api.patch(f"/api/v1/tasks/{overdue['id']}", headers=emp, json={"status": "FILED", "filing_reference": "ACK1"})
    assert r.json()["filed_at"] is not None


def test_document_request_flow_via_portal(api, firm: Firm, db):
    c = firm.client("Sunita", "9876600001")
    task = api.post("/api/v1/tasks", headers=firm.h, json={"client_id": c["id"], "title": "ITR FY 2025-26", "service_type": "ITR"}).json()
    r = api.post(
        "/api/v1/document-requests",
        headers=firm.h,
        json={
            "client_id": c["id"],
            "task_id": task["id"],
            "title": "ITR Filing",
            "due_date": str(date.today() + timedelta(days=5)),
            "items": [{"name": "Bank Statement", "document_type": "BANK_STATEMENT"}, {"name": "Form 16", "document_type": "TDS_DOCUMENT"}],
        },
    )
    assert r.status_code == 201
    req = r.json()
    assert req["status"] == "PENDING" and req["notified_at"]
    assert api.get(f"/api/v1/tasks/{task['id']}", headers=firm.h).json()["status"] == "DOCUMENTS_PENDING"
    ph = firm.portal_login(c["phone"])
    item1, _item2 = req["items"]
    r = api.post(
        f"/api/v1/portal/document-requests/{req['id']}/upload",
        headers=ph,
        files={"file": ("bank.pdf", make_pdf("bank"), "application/pdf")},
        data={"item_id": item1["id"]},
    )
    assert r.status_code == 200 and r.json()["status"] == "PARTIAL"
    r = api.post(
        f"/api/v1/portal/document-requests/{req['id']}/upload",
        headers=ph,
        files={"file": ("form16.pdf", make_pdf("f16"), "application/pdf")},
    )
    assert r.json()["status"] == "COMPLETE"
    assert api.get(f"/api/v1/tasks/{task['id']}", headers=firm.h).json()["status"] == "DOCUMENTS_RECEIVED"
    docs = api.get("/api/v1/documents", headers=firm.h, params={"source": "CLIENT_PORTAL"}).json()
    assert docs["total"] == 2
    # client cannot upload to another client's request
    other = firm.client("Other", "9876600002")
    req2 = api.post(
        "/api/v1/document-requests", headers=firm.h, json={"client_id": other["id"], "title": "X request", "items": [{"name": "PAN"}]}
    ).json()
    r = api.post(
        f"/api/v1/portal/document-requests/{req2['id']}/upload", headers=ph, files={"file": ("x.pdf", make_pdf(), "application/pdf")}
    )
    assert r.status_code == 404


def test_document_request_overdue_marking(api, firm: Firm, db):
    from app.services.reminders import run_reminders

    c = firm.client()
    api.post(
        "/api/v1/document-requests",
        headers=firm.h,
        json={
            "client_id": c["id"],
            "title": "Late",
            "due_date": str(date.today() - timedelta(days=1)),
            "items": [{"name": "PAN"}],
            "notify_client": False,
        },
    )
    run_reminders(db)
    assert api.get("/api/v1/document-requests", headers=firm.h).json()["items"][0]["status"] == "OVERDUE"

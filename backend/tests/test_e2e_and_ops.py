"""Core end-to-end scenario (spec §74) plus audit, reports, reminders and health."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from conftest import Firm, last_outbound, make_pdf

from app.models import AuditLog


def test_core_end_to_end_scenario(api, db):
    # Create Organization + Admin
    firm = Firm(api, "E2E Associates")
    # Create Client
    client = firm.client("Rahul Mehta", "9876543210")
    other = firm.client("Sunita Verma", "9876543211")
    # Upload ITR document
    content = make_pdf("ITR-V Acknowledgement AY 2026-27")
    doc = firm.upload(client["id"], name="ITR-V_FY2025-26.pdf", content=content, document_type="ITR_ACKNOWLEDGEMENT").json()
    other_doc = firm.upload(other["id"], name="Other.pdf", document_type="ITR_ACKNOWLEDGEMENT").json()
    # Approve document → WhatsApp notification generated → mock WhatsApp receives message
    from app.integrations.whatsapp.mock import OUTBOX

    OUTBOX.clear()
    assert api.post(f"/api/v1/documents/{doc['id']}/approve", headers=firm.h).status_code == 200
    sent = [m for m in OUTBOX.messages if m["type"] == "template" and m["template"] == "prodesk_document_ready"]
    assert len(sent) == 1 and sent[0]["to"] == "919876543210"
    token = sent[0]["url_suffix"].removeprefix("link/")
    assert client["name"] in sent[0]["body_params"]
    # Client also requests the document over WhatsApp → backend identifies client → file sent in the chat
    OUTBOX.clear()
    firm.inbound(client["phone"], "Mujhe ITR acknowledgement bhejo")
    files = [m for m in OUTBOX.messages if m["type"] == "document"]
    assert len(files) == 1 and files[0]["to"] == "919876543210" and files[0]["file_name"] == "ITR-V_FY2025-26.pdf"
    assert api.get(files[0]["link"].replace("http://testserver", "")).content == content
    link_token = token
    # Client opens secure link: public info reveals nothing about the document
    info = api.get(f"/api/v1/portal/link/{link_token}").json()
    assert info["org_slug"] == firm.slug and "ITR" not in str(info) and info["phone_hint"].endswith("3210")
    # Download requires authentication — phone number alone is not enough
    assert api.post(f"/api/v1/portal/link/{link_token}/download").status_code == 401
    # Client authenticates (OTP over WhatsApp)
    ph = firm.portal_login(client["phone"])
    # Authorization succeeds → secure document URL generated → client accesses document
    r = api.post(f"/api/v1/portal/link/{token}/download", headers=ph)
    assert r.status_code == 200
    f = api.get(r.json()["url"].replace("http://testserver", ""))
    assert f.status_code == 200 and f.content == content
    assert api.post(f"/api/v1/portal/link/{link_token}/download", headers=ph).status_code == 200
    # Audit log created
    db.expire_all()
    logs = db.query(AuditLog).filter(AuditLog.resource_id == doc["id"], AuditLog.action == "DOCUMENT_DOWNLOADED").all()
    assert len(logs) == 2 and all(log.actor_type == "CLIENT" and str(log.client_id) == client["id"] for log in logs)
    detail = api.get(f"/api/v1/documents/{doc['id']}", headers=firm.h).json()
    assert any(d["downloaded_at"] for d in detail["deliveries"])

    # Client A cannot access Client B's document
    other_link = None
    api.post(f"/api/v1/documents/{other_doc['id']}/approve", headers=firm.h)
    for m in OUTBOX.messages:
        if m["type"] == "template" and m["to"] == "919876543211":
            other_link = m["url_suffix"].removeprefix("link/")
    assert other_link
    assert api.post(f"/api/v1/portal/link/{other_link}/download", headers=ph).status_code == 404
    assert api.post(f"/api/v1/portal/documents/{other_doc['id']}/download-url", headers=ph).status_code == 404
    assert [d["id"] for d in api.get("/api/v1/portal/documents", headers=ph).json()["items"]] == [doc["id"]]

    # Organization A cannot access Organization B's data
    firm_b = Firm(api, "Other Org")
    assert api.get(f"/api/v1/documents/{doc['id']}", headers=firm_b.h).status_code == 404
    assert api.get(f"/api/v1/clients/{client['id']}", headers=firm_b.h).status_code == 404
    assert api.post(f"/api/v1/portal/link/{token}/download", headers=firm_b.h).status_code == 403  # staff token on portal
    # A client of org B cannot use org A's delivery link
    cb = firm_b.client("Rahul Mehta", "9876543210")  # same phone, different firm
    ph_b = firm_b.portal_login(cb["phone"])
    assert api.post(f"/api/v1/portal/link/{token}/download", headers=ph_b).status_code == 404


def test_client_cannot_download_unapproved_or_staff_drafts(api, firm: Firm):
    c = firm.client("Draft Client", "9876511111")
    draft = firm.upload(c["id"]).json()
    ph = firm.portal_login(c["phone"])
    assert api.get("/api/v1/portal/documents", headers=ph).json()["total"] == 0
    r = api.post(f"/api/v1/portal/documents/{draft['id']}/download-url", headers=ph)
    assert r.status_code == 404  # unapproved staff drafts are invisible to clients


def test_otp_security(api, firm: Firm):
    c = firm.client("Otp Client", "9876522222")
    r = api.post("/api/v1/portal/auth/request-otp", json={"org_slug": firm.slug, "phone": "9000000000"})
    assert r.status_code == 200 and r.json()["dev_otp"] is None  # unknown number: same response, nothing sent
    r = api.post("/api/v1/portal/auth/request-otp", json={"org_slug": firm.slug, "phone": c["phone"]})
    code = r.json()["dev_otp"]
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(5):
        assert (
            api.post("/api/v1/portal/auth/verify-otp", json={"org_slug": firm.slug, "phone": c["phone"], "code": wrong}).status_code == 401
        )
    # locked after max attempts even with the right code
    assert api.post("/api/v1/portal/auth/verify-otp", json={"org_slug": firm.slug, "phone": c["phone"], "code": code}).status_code == 401
    # rate limit on OTP requests per phone
    codes = [api.post("/api/v1/portal/auth/request-otp", json={"org_slug": firm.slug, "phone": c["phone"]}).status_code for _ in range(4)]
    assert 429 in codes


def test_otp_message_body_is_redacted(api, firm: Firm, db):
    from app.models import Message

    c = firm.client("Redact", "9876533333")
    code = api.post("/api/v1/portal/auth/request-otp", json={"org_slug": firm.slug, "phone": c["phone"]}).json()["dev_otp"]
    db.expire_all()
    for m in db.query(Message).filter(Message.template_key == "OTP").all():
        assert code not in (m.body or "") and code not in str(m.payload)


def test_audit_logs_have_no_secrets(api, firm: Firm, db):
    from conftest import PASSWORD

    api.post("/api/v1/auth/login", json={"email": firm.admin_email, "password": PASSWORD})
    c = firm.client()
    firm.upload(c["id"])
    db.expire_all()
    actions = {a.action for a in db.query(AuditLog).filter(AuditLog.organization_id == firm.org_id).all()}
    assert {"ORG_CREATED", "LOGIN", "CLIENT_CREATED", "DOCUMENT_UPLOADED"} <= actions
    dump = " ".join(str(a.metadata_) for a in db.query(AuditLog).all())
    assert PASSWORD not in dump and "access_token" not in dump


def test_reports_and_csv_export(api, firm: Firm):
    c = firm.client("Report Client", "9876544444")
    api.post(
        "/api/v1/tasks", headers=firm.h, json={"client_id": c["id"], "title": "Late", "due_date": str(date.today() - timedelta(days=3))}
    )
    dash = api.get("/api/v1/reports/dashboard", headers=firm.h).json()
    assert dash["total_clients"] == 1 and dash["overdue_tasks"] == 1
    for name in api.get("/api/v1/reports", headers=firm.h).json():
        r = api.get(f"/api/v1/reports/{name}", headers=firm.h)
        assert r.status_code == 200, name
        assert "columns" in r.json()
    csv = api.get("/api/v1/reports/overdue-tasks/csv", headers=firm.h)
    assert csv.status_code == 200 and csv.headers["content-type"].startswith("text/csv") and "Report Client" in csv.text


def test_csv_formula_injection_neutralised():
    from app.services.reports import to_csv

    out = to_csv({"columns": ["client"], "rows": [{"client": '=HYPERLINK("http://evil")'}]})
    assert "'=HYPERLINK" in out


def test_reminders_respect_frequency_max_quiet_hours_and_opt_out(api, firm: Firm, db):
    from app.models import DocumentRequest, Organization
    from app.services.reminders import run_reminders

    c = firm.client("Remind Me", "9876555555")
    opted_out = firm.client("No Remind", "9876555556")
    api.patch(f"/api/v1/clients/{opted_out['id']}", headers=firm.h, json={"whatsapp_opt_in": False})
    for cl in (c, opted_out):
        api.post(
            "/api/v1/document-requests",
            headers=firm.h,
            json={"client_id": cl["id"], "title": "Docs", "items": [{"name": "PAN"}], "notify_client": False},
        )
    org = db.get(Organization, firm.org_id)
    org.settings = {
        **(org.settings or {}),
        "reminders": {"frequency_hours": 24, "max_reminders": 2, "quiet_hours_start": "22:00", "quiet_hours_end": "07:00"},
    }
    db.commit()
    noon_ist = datetime.now(UTC).replace(hour=6, minute=30)  # 12:00 IST
    later = noon_ist + timedelta(days=2)
    db.query(DocumentRequest).update({DocumentRequest.created_at: noon_ist - timedelta(days=3)})
    db.commit()
    assert run_reminders(db, now=noon_ist)["document_requests"] == 1  # only the opted-in client
    assert run_reminders(db, now=noon_ist + timedelta(hours=1))["document_requests"] == 0  # frequency
    quiet = noon_ist.replace(hour=18)  # 23:30 IST
    assert run_reminders(db, now=quiet + timedelta(days=1))["document_requests"] == 0  # quiet hours
    assert run_reminders(db, now=later)["document_requests"] == 1
    assert run_reminders(db, now=later + timedelta(days=2))["document_requests"] == 0  # max reminders reached
    assert "still pending" in last_outbound(db, firm.org_id, "Reminder").body


def test_compliance_requires_source_for_verified_dates(api, firm: Firm):
    d = str(date.today() + timedelta(days=5))
    r = api.post(
        "/api/v1/compliance", headers=firm.h, json={"category": "GST", "title": "GSTR-3B", "due_date": d, "source": "VERIFIED_SOURCE"}
    )
    assert r.status_code == 422
    r = api.post(
        "/api/v1/compliance",
        headers=firm.h,
        json={
            "category": "GST",
            "title": "GSTR-3B",
            "due_date": d,
            "source": "VERIFIED_SOURCE",
            "source_reference": "https://www.gst.gov.in/",
        },
    )
    assert r.status_code == 201 and r.json()["verified_by"] == firm.admin_id
    assert len(api.get("/api/v1/compliance", headers=firm.h).json()) == 1


def test_health_endpoints(api):
    assert api.get("/health").json()["status"] == "ok"
    r = api.get("/health/ready")
    assert r.status_code == 200
    checks = r.json()["checks"]
    assert checks["database"]["ok"] and checks["redis"]["ok"] and checks["storage"]["ok"]
    assert checks["providers"] == {"whatsapp": "mock", "ai": "mock", "payments": "mock", "storage": "local"}


def test_openapi_and_request_id(api):
    r = api.get("/openapi.json")
    assert r.status_code == 200 and "/api/v1/documents" in r.json()["paths"]
    r = api.get("/health", headers={"X-Request-ID": "abc123"})
    assert r.headers["x-request-id"] == "abc123"
    err = api.get("/api/v1/clients")
    assert err.json()["request_id"] and err.headers["x-content-type-options"] == "nosniff"

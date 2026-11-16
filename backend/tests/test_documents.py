from __future__ import annotations

import io
import time
import zipfile

from conftest import PNG_BYTES, Firm, last_outbound, make_pdf


def test_upload_and_metadata(api, firm: Firm):
    c = firm.client()
    r = firm.upload(c["id"], name="../../etc/passwd ITR?.pdf")
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["status"] == "UPLOADED" and d["version"] == 1 and d["mime_type"] == "application/pdf"
    assert "/" not in d["file_name"] and ".." not in d["file_name"].split(".")[0]
    detail = api.get(f"/api/v1/documents/{d['id']}", headers=firm.h).json()
    assert len(detail["versions"]) == 1 and len(detail["versions"][0]["checksum_sha256"]) == 64
    assert "storage_key" not in d and "storage_key" not in detail  # never exposed
    # document processing job extracted metadata
    assert "v1" in detail["extracted_metadata"]


def test_rejects_disguised_and_unsupported_files(api, firm: Firm):
    c = firm.client()
    exe = b"MZ\x90\x00" + b"\x00" * 100
    r = firm.upload(c["id"], name="invoice.pdf", content=exe)
    assert r.status_code == 422 and r.json()["error"]["code"] == "FILE_TYPE_MISMATCH"
    r = firm.upload(c["id"], name="script.html", content=b"<script>alert(1)</script>")
    assert r.status_code == 422 and r.json()["error"]["code"] == "UNSUPPORTED_FILE"
    # macro-enabled office file disguised as xlsx
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("xl/workbook.xml", "<x/>")
        z.writestr("xl/vbaProject.bin", "evil")
    assert firm.upload(c["id"], name="sheet.xlsx", content=buf.getvalue()).status_code == 422
    # valid xlsx & png accepted
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("xl/workbook.xml", "<x/>")
    assert firm.upload(c["id"], name="sheet.xlsx", content=buf.getvalue()).status_code == 201
    assert firm.upload(c["id"], name="pan.png", content=PNG_BYTES, document_type="PAN").status_code == 201


def test_size_limit(api, firm: Firm, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "MAX_UPLOAD_MB", 1)
    c = firm.client()
    r = firm.upload(c["id"], content=make_pdf() + b"0" * (1024 * 1024 + 10))
    assert r.status_code == 422 and r.json()["error"]["code"] == "FILE_TOO_LARGE"


def test_review_approve_and_auto_delivery(api, firm: Firm, db):
    c = firm.client("Rahul Mehta", "9876543210")
    d = firm.upload(c["id"], document_type="BALANCE_SHEET").json()
    assert api.post(f"/api/v1/documents/{d['id']}/submit", headers=firm.h).json()["status"] == "UNDER_REVIEW"
    r = api.post(f"/api/v1/documents/{d['id']}/approve", headers=firm.h, json={"note": "ok"})
    assert r.status_code == 200
    detail = api.get(f"/api/v1/documents/{d['id']}", headers=firm.h).json()
    assert detail["status"] == "DELIVERED"
    assert detail["deliveries"][0]["status"] == "SENT" and detail["deliveries"][0]["sent_at"]
    msg = last_outbound(db, firm.org_id, "Balance Sheet")
    assert msg is not None and msg.template_key == "DOCUMENT_READY" and msg.status == "SENT"
    assert msg.payload["url_suffix"].startswith("link/")
    actions = [a["action"] for a in detail["access_history"]]
    assert {"DOCUMENT_UPLOADED", "DOCUMENT_APPROVED", "DOCUMENT_DELIVERY_CREATED"} <= set(actions)


def test_reject_and_invalid_transitions(api, firm: Firm):
    c = firm.client()
    d = firm.upload(c["id"]).json()
    r = api.post(f"/api/v1/documents/{d['id']}/reject", headers=firm.h, json={"reason": "Wrong year"})
    assert r.json()["status"] == "REJECTED"
    assert api.post(f"/api/v1/documents/{d['id']}/approve", headers=firm.h).status_code == 422
    assert api.post(f"/api/v1/documents/{d['id']}/deliver", headers=firm.h).status_code == 422


def test_versioning_keeps_history_and_resets_approval(api, firm: Firm):
    c = firm.client()
    d = firm.upload(c["id"]).json()
    api.post(f"/api/v1/documents/{d['id']}/approve", headers=firm.h, json={"deliver": False})
    r = api.post(
        f"/api/v1/documents/{d['id']}/versions", headers=firm.h, files={"file": ("ITR_Ack_v2.pdf", make_pdf("v2"), "application/pdf")}
    )
    assert r.status_code == 201
    doc = r.json()
    assert doc["version"] == 2 and doc["status"] == "UPLOADED" and doc["approved_version_id"] is None
    r = api.post(
        f"/api/v1/documents/{d['id']}/versions", headers=firm.h, files={"file": ("ITR_Ack_v3.pdf", make_pdf("v3"), "application/pdf")}
    )
    detail = api.get(f"/api/v1/documents/{d['id']}", headers=firm.h).json()
    assert [v["version_number"] for v in detail["versions"]] == [1, 2, 3]
    assert [v["status"] for v in detail["versions"]] == ["SUPERSEDED", "SUPERSEDED", "UPLOADED"]
    # delivery refuses until the current version is approved
    assert api.post(f"/api/v1/documents/{d['id']}/deliver", headers=firm.h).status_code == 422
    api.post(f"/api/v1/documents/{d['id']}/approve", headers=firm.h, json={"deliver": False})
    dl = api.post(f"/api/v1/documents/{d['id']}/deliver", headers=firm.h).json()
    assert dl["version_id"] == detail["versions"][2]["id"]
    # old versions still downloadable by staff (auditable)
    v1 = detail["versions"][0]["id"]
    assert api.post(f"/api/v1/documents/{d['id']}/download-url", headers=firm.h, params={"version_id": v1}).status_code == 200


def test_signed_url_download_and_tampering(api, firm: Firm):
    c = firm.client()
    content = make_pdf("secret content")
    d = firm.upload(c["id"], content=content).json()
    r = api.post(f"/api/v1/documents/{d['id']}/download-url", headers=firm.h)
    assert r.status_code == 200
    url = r.json()["url"].replace("http://testserver", "")
    f = api.get(url)
    assert f.status_code == 200 and f.content == content
    assert f.headers["content-disposition"].startswith("attachment")
    assert f.headers["x-content-type-options"] == "nosniff"
    # tampered / guessed token
    assert api.get(url[:-3] + "abc").status_code == 401
    assert api.get("/api/v1/files/" + "a" * 40).status_code == 401


def test_expired_signed_url(api, firm: Firm):
    from app.core.security import create_signed_download_token
    from app.models import DocumentVersion

    c = firm.client()
    d = firm.upload(c["id"]).json()
    from app.db.session import SessionLocal

    with SessionLocal() as s:
        v = s.query(DocumentVersion).filter_by(document_id=d["id"]).one()
        token = create_signed_download_token(version_id=str(v.id), org_id=str(v.organization_id), disposition="attachment", ttl_seconds=1)
    time.sleep(2)
    r = api.get(f"/api/v1/files/{token}")
    assert r.status_code == 401 and r.json()["error"]["code"] == "LINK_EXPIRED"


def test_signed_token_cannot_cross_orgs(api, firm: Firm, other_firm: Firm):
    from app.core.security import create_signed_download_token
    from app.db.session import SessionLocal
    from app.models import DocumentVersion

    c = other_firm.client()
    d = other_firm.upload(c["id"]).json()
    with SessionLocal() as s:
        v = s.query(DocumentVersion).filter_by(document_id=d["id"]).one()
        forged = create_signed_download_token(version_id=str(v.id), org_id=firm.org_id, disposition="attachment")
    assert api.get(f"/api/v1/files/{forged}").status_code == 404


def test_delete_makes_document_inaccessible_and_purges_storage(api, firm: Firm):
    from app.db.session import SessionLocal
    from app.integrations.storage import get_storage
    from app.models import DocumentVersion

    c = firm.client()
    d = firm.upload(c["id"]).json()
    url = api.post(f"/api/v1/documents/{d['id']}/download-url", headers=firm.h).json()["url"].replace("http://testserver", "")
    assert api.delete(f"/api/v1/documents/{d['id']}", headers=firm.h).status_code == 204
    assert api.get(f"/api/v1/documents/{d['id']}", headers=firm.h).status_code == 404
    assert api.get(url).status_code == 404  # outstanding signed URL no longer works
    with SessionLocal() as s:
        v = s.query(DocumentVersion).filter_by(document_id=d["id"]).one()
        assert v.storage_deleted_at is not None and not get_storage().exists(v.storage_key)


def test_search_filter_pagination(api, firm: Firm):
    c = firm.client()
    for i in range(7):
        firm.upload(c["id"], name=f"GST_Return_{i}.pdf", document_type="GST_RETURN", fy="2024-25")
    firm.upload(c["id"], name="BalanceSheet.pdf", document_type="BALANCE_SHEET")
    r = api.get("/api/v1/documents", headers=firm.h, params={"document_type": "GST_RETURN", "page_size": 5}).json()
    assert r["total"] == 7 and len(r["items"]) == 5
    assert api.get("/api/v1/documents", headers=firm.h, params={"q": "balance"}).json()["total"] == 1
    assert api.get("/api/v1/documents", headers=firm.h, params={"financial_year": "2024-25", "page": 2, "page_size": 5}).json()["items"]

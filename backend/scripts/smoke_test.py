"""End-to-end smoke test against a RUNNING ProDesk stack (API + worker) on mock providers.

    python scripts/smoke_test.py --api http://localhost:8000 [--app-secret <WHATSAPP_APP_SECRET>]

Exercises: register firm → create client → upload ITR → approve → WhatsApp (mock) delivery →
client asks on WhatsApp (signed webhook) → bot reply with secure link → client OTP login →
signed download → audit trail → tenant isolation.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import re
import sys
import time
import uuid

import httpx


def pdf(text: str) -> bytes:
    body = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET"
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>", f"<< /Length {len(body)} >>\nstream\n{body}\nendstream"]
    out, offs = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += f"{i} 0 obj\n{o}\nendobj\n".encode()
    x = len(out)
    out += f"xref\n0 {len(objs)+1}\n0000000000 65535 f \n".encode() + b"".join(f"{o:010d} 00000 n \n".encode() for o in offs)
    return out + f"trailer\n<< /Size {len(objs)+1} /Root 1 0 R >>\nstartxref\n{x}\n%%EOF\n".encode()


def wait_for(fn, what: str, timeout: float = 20.0):  # type: ignore[no-untyped-def]
    end = time.time() + timeout
    while time.time() < end:
        v = fn()
        if v:
            return v
        time.sleep(0.5)
    raise SystemExit(f"FAIL: timed out waiting for {what}")


def ok(msg: str) -> None:
    print(f"  ✔ {msg}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--app-secret", default="")
    a = ap.parse_args()
    c = httpx.Client(base_url=a.api + "/api/v1", timeout=20)
    tag = uuid.uuid4().hex[:6]

    r = httpx.get(a.api + "/health/ready", timeout=10)
    assert r.status_code == 200, r.text
    ok(f"readiness: {r.json()['checks']['providers']}")

    r = c.post("/auth/register", json={"firm_name": f"Smoke CA {tag}", "admin_name": "Smoke Admin",
                                       "email": f"smoke-{tag}@example.com", "password": "Smoke-Pass-123"})
    assert r.status_code == 201, r.text
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    me = c.get("/auth/me", headers=h).json()
    ok(f"firm registered ({me['organization_slug']})")
    pnid = f"smoke-pnid-{tag}"
    assert c.put("/whatsapp/account", headers=h, json={"provider": "mock", "phone_number_id": pnid}).status_code == 200

    phone = f"98{int(tag, 16) % 10**8:08d}"
    cl = c.post("/clients", headers=h, json={"name": "Smoke Client", "phone": phone, "whatsapp_opt_in": True}).json()
    ok(f"client created {cl['phone']}")

    content = pdf("Smoke ITR-V acknowledgement")
    d = c.post("/documents", headers=h, files={"file": ("ITR-V.pdf", content, "application/pdf")},
               data={"client_id": cl["id"], "document_type": "ITR_ACKNOWLEDGEMENT", "financial_year": "2025-26"}).json()
    assert c.post(f"/documents/{d['id']}/approve", headers=h, json={}).status_code == 200
    det = wait_for(lambda: (x := c.get(f"/documents/{d['id']}", headers=h).json())["status"] == "DELIVERED" and x,
                   "worker to deliver document on WhatsApp")
    ok(f"approved → worker delivered via WhatsApp (delivery {det['deliveries'][0]['status']})")

    body = {"object": "whatsapp_business_account", "entry": [{"id": "x", "changes": [{"field": "messages", "value": {
        "metadata": {"phone_number_id": pnid}, "contacts": [{"profile": {"name": "Smoke"}, "wa_id": "91" + phone}],
        "messages": [{"from": "91" + phone, "id": f"wamid.SMOKE{tag}", "timestamp": str(int(time.time())), "type": "text",
                      "text": {"body": "Mujhe ITR acknowledgement bhejo"}}]}}]}]}
    raw = json.dumps(body).encode()
    sig = "sha256=" + hmac.new(a.app_secret.encode(), raw, hashlib.sha256).hexdigest()
    assert c.post("/webhooks/whatsapp", content=raw, headers={"X-Hub-Signature-256": "sha256=bad"}).status_code == 401
    ok("unsigned/forged webhook rejected (401)")
    r = c.post("/webhooks/whatsapp", content=raw, headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"})
    assert r.status_code == 200, r.text
    r2 = c.post("/webhooks/whatsapp", content=raw, headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"})
    assert r2.json()["accepted"] == 0
    ok("signed webhook accepted; duplicate ignored")

    def bot_link() -> str | None:
        convs = c.get("/conversations", headers=h).json()["items"]
        if not convs:
            return None
        msgs = c.get(f"/conversations/{convs[0]['id']}/messages", headers=h).json()["items"]
        for m in msgs:
            if m["sender"] == "BOT" and m["status"] == "SENT" and (mm := re.search(r"/portal/link/([\w\-]+)", m["body"] or "")):
                return mm.group(1)
        return None
    token = wait_for(bot_link, "worker to process webhook and reply")
    ok("worker processed message; assistant replied with secure link")

    assert c.post(f"/portal/link/{token}/download").status_code == 401
    ok("link download without OTP → 401")
    otp = c.post("/portal/auth/request-otp", json={"org_slug": me["organization_slug"], "phone": phone}).json()["dev_otp"]
    s = c.post("/portal/auth/verify-otp", json={"org_slug": me["organization_slug"], "phone": phone, "code": otp}).json()
    ph = {"Authorization": f"Bearer {s['access_token']}"}
    url = c.post(f"/portal/link/{token}/download", headers=ph).json()["url"]
    f = httpx.get(url, timeout=10)
    assert f.status_code == 200 and f.content == content
    ok("client OTP login → signed URL → file downloaded (bytes match)")

    logs = c.get("/audit-logs", headers=h, params={"resource_id": d["id"]}).json()["items"]
    assert any(x["action"] == "DOCUMENT_DOWNLOADED" and x["actor_type"] == "CLIENT" for x in logs)
    ok("audit log: DOCUMENT_DOWNLOADED by CLIENT")

    r = c.post("/auth/register", json={"firm_name": f"Other CA {tag}", "admin_name": "Other", "email": f"other-{tag}@example.com",
                                       "password": "Smoke-Pass-123"})
    h2 = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert c.get(f"/documents/{d['id']}", headers=h2).status_code == 404
    assert c.get(f"/clients/{cl['id']}", headers=h2).status_code == 404
    ok("organization B cannot see organization A's client or document (404)")
    print("SMOKE TEST PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())

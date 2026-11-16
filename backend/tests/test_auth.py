from __future__ import annotations

import re

from conftest import PASSWORD, Firm

from app.integrations.email import get_email_provider


def test_register_login_me(api, firm: Firm):
    r = api.post("/api/v1/auth/login", json={"email": firm.admin_email, "password": PASSWORD})
    assert r.status_code == 200
    body = r.json()
    assert body["access_token"] and body["refresh_token"]
    me = api.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"}).json()
    assert me["role"] == "FIRM_ADMIN"
    assert "SETTINGS_MANAGE" in me["permissions"]


def test_wrong_password_and_unknown_user_same_error(api, firm: Firm):
    a = api.post("/api/v1/auth/login", json={"email": firm.admin_email, "password": "wrong-password-1"})
    b = api.post("/api/v1/auth/login", json={"email": "nobody@x.example.com", "password": "wrong-password-1"})
    assert a.status_code == b.status_code == 401
    assert a.json()["error"]["code"] == b.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_invalid_and_missing_token(api):
    assert api.get("/api/v1/clients").status_code == 401
    r = api.get("/api/v1/clients", headers={"Authorization": "Bearer not.a.jwt"})
    assert r.status_code == 401 and r.json()["error"]["code"] == "INVALID_TOKEN"
    import jwt

    forged = jwt.encode({"sub": "x", "typ": "staff", "exp": 9999999999}, "wrong-secret-wrong-secret-wrong-secret!", algorithm="HS256")
    assert api.get("/api/v1/clients", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_expired_token_rejected(api, firm: Firm):
    from datetime import timedelta

    from app.core.security import create_access_token

    tok, _, _ = create_access_token(subject=firm.admin_id, typ="staff", org_id=firm.org_id, extra={"ver": 0}, ttl=timedelta(seconds=-5))
    r = api.get("/api/v1/clients", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 401 and r.json()["error"]["code"] == "TOKEN_EXPIRED"


def test_refresh_rotation_and_reuse_detection(api, firm: Firm):
    r = api.post("/api/v1/auth/login", json={"email": firm.admin_email, "password": PASSWORD})
    rt1 = r.json()["refresh_token"]
    r2 = api.post("/api/v1/auth/refresh", json={"refresh_token": rt1})
    assert r2.status_code == 200
    rt2 = r2.json()["refresh_token"]
    assert rt2 != rt1
    # Reusing the old (rotated) token revokes the whole family
    r3 = api.post("/api/v1/auth/refresh", json={"refresh_token": rt1})
    assert r3.status_code == 401 and r3.json()["error"]["code"] == "TOKEN_REUSED"
    assert api.post("/api/v1/auth/refresh", json={"refresh_token": rt2}).status_code == 401


def test_logout_revokes_access_token(api, firm: Firm):
    r = api.post("/api/v1/auth/login", json={"email": firm.admin_email, "password": PASSWORD})
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert api.post("/api/v1/auth/logout", headers=h, json={"refresh_token": r.json()["refresh_token"]}).status_code == 200
    assert api.get("/api/v1/clients", headers=h).status_code == 401
    assert api.post("/api/v1/auth/refresh", json={"refresh_token": r.json()["refresh_token"]}).status_code == 401


def test_password_reset_flow(api, firm: Firm):
    outbox = get_email_provider().outbox  # type: ignore[attr-defined]
    outbox.clear()
    assert api.post("/api/v1/auth/password-reset/request", json={"email": firm.admin_email}).status_code == 200
    assert api.post("/api/v1/auth/password-reset/request", json={"email": "ghost@x.example.com"}).status_code == 200  # no enumeration
    assert len(outbox) == 1
    token = re.search(r"token=([\w\-]+)", outbox[0]["body"]).group(1)
    r = api.post("/api/v1/auth/password-reset/confirm", json={"token": token, "new_password": "N3w-Password-99"})
    assert r.status_code == 200
    # old session invalidated, old password rejected, token single-use
    assert api.get("/api/v1/clients", headers=firm.h).status_code == 401
    assert api.post("/api/v1/auth/login", json={"email": firm.admin_email, "password": PASSWORD}).status_code == 401
    assert api.post("/api/v1/auth/login", json={"email": firm.admin_email, "password": "N3w-Password-99"}).status_code == 200
    assert api.post("/api/v1/auth/password-reset/confirm", json={"token": token, "new_password": "Another-Pass-1"}).status_code == 422


def test_invite_and_activate_employee(api, firm: Firm):
    outbox = get_email_provider().outbox  # type: ignore[attr-defined]
    outbox.clear()
    r = api.post("/api/v1/users", headers=firm.h, json={"email": "new.emp@alpha.example.com", "full_name": "New Emp", "role": "EMPLOYEE"})
    assert r.status_code == 201
    assert api.post("/api/v1/auth/login", json={"email": "new.emp@alpha.example.com", "password": PASSWORD}).status_code == 401
    token = re.search(r"token=([\w\-]+)", outbox[-1]["body"]).group(1)
    assert api.post("/api/v1/auth/activate", json={"token": token, "password": PASSWORD}).status_code == 200
    r = api.post("/api/v1/auth/login", json={"email": "new.emp@alpha.example.com", "password": PASSWORD})
    assert r.status_code == 200
    me = api.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"}).json()
    assert me["role"] == "EMPLOYEE" and "USER_MANAGE" not in me["permissions"]


def test_login_lockout_and_rate_limit(api, firm: Firm):
    codes = [api.post("/api/v1/auth/login", json={"email": firm.admin_email, "password": "bad-password-x"}).status_code for _ in range(12)]
    assert 429 in codes  # per-IP rate limit
    from app.core.redis import get_redis

    get_redis().flushdb()
    r = api.post("/api/v1/auth/login", json={"email": firm.admin_email, "password": PASSWORD})
    assert r.status_code == 401 and r.json()["error"]["code"] == "ACCOUNT_LOCKED"


def test_weak_password_rejected(api):
    r = api.post(
        "/api/v1/auth/register", json={"firm_name": "Weak", "admin_name": "W", "email": "w@w.example.com", "password": "aaaaaaaaaaaa"}
    )
    assert r.status_code == 422

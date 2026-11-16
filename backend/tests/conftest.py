"""Test harness: real PostgreSQL + Redis, schema built by Alembic migrations, Celery eager."""

from __future__ import annotations

import os
import tempfile
import uuid
from collections.abc import Iterator
from typing import Any

os.environ.update(
    {
        "APP_ENV": "test",
        "DATABASE_URL": os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://postgres@/prodesk_test?host=/tmp"),
        "REDIS_URL": os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/15"),
        "CELERY_TASK_ALWAYS_EAGER": "true",
        "WHATSAPP_PROVIDER": "mock",
        "WHATSAPP_APP_SECRET": "test-app-secret",
        "WHATSAPP_VERIFY_TOKEN": "test-verify-token",
        "AI_PROVIDER": "mock",
        "PAYMENT_PROVIDER": "mock",
        "MOCK_PAYMENT_SECRET": "test-mock-pay-secret",
        "STORAGE_PROVIDER": "local",
        "LOCAL_STORAGE_PATH": tempfile.mkdtemp(prefix="prodesk-test-"),
        "LOG_JSON": "false",
        "LOG_LEVEL": "WARNING",
        "SECRET_KEY": "test-secret-key-that-is-long-enough-1234567890",
        "PUBLIC_API_URL": "http://testserver",
        "FRONTEND_URL": "http://frontend.test",
    }
)

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app.core.redis import get_redis
from app.db.session import SessionLocal, engine
from app.main import app

BACKEND = os.path.dirname(os.path.dirname(__file__))
PASSWORD = "Str0ng-Passw0rd!"


def make_pdf(text_: str = "Test document") -> bytes:
    from app.cli import make_pdf as _mk

    return _mk(text_)


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


@pytest.fixture(scope="session", autouse=True)
def _schema() -> Iterator[None]:
    with engine.begin() as c:
        c.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    cfg = Config(os.path.join(BACKEND, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(BACKEND, "migrations"))
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
def _clean() -> Iterator[None]:
    from app.integrations.email import get_email_provider
    from app.integrations.whatsapp.mock import OUTBOX

    with engine.begin() as c:
        tables = (
            c.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename <> 'alembic_version'")).scalars().all()
        )
        c.execute(text("TRUNCATE " + ", ".join(f'"{t}"' for t in tables) + " RESTART IDENTITY CASCADE"))
    get_redis().flushdb()
    OUTBOX.clear()
    email = get_email_provider()
    if hasattr(email, "outbox"):
        email.outbox.clear()
    from app.services.rbac import sync_system_roles

    with SessionLocal() as db:
        sync_system_roles(db)
        db.commit()
    yield


@pytest.fixture
def api() -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db() -> Iterator[Any]:
    s = SessionLocal()
    yield s
    s.close()


# --- helpers ---------------------------------------------------------------------------


class Firm:
    def __init__(self, api: TestClient, name: str) -> None:
        self.api = api
        email = f"admin-{uuid.uuid4().hex[:8]}@{name.lower().replace(' ', '')}.example.com"
        r = api.post("/api/v1/auth/register", json={"firm_name": name, "admin_name": f"{name} Admin", "email": email, "password": PASSWORD})
        assert r.status_code == 201, r.text
        self.admin_email = email
        self.token = r.json()["access_token"]
        self.h = {"Authorization": f"Bearer {self.token}"}
        me = api.get("/api/v1/auth/me", headers=self.h).json()
        self.org_id = me["organization_id"]
        self.slug = me["organization_slug"]
        self.admin_id = me["id"]
        # mock WhatsApp account so webhooks route to this org
        self.phone_number_id = f"pnid-{uuid.uuid4().hex[:10]}"
        r = api.put("/api/v1/whatsapp/account", headers=self.h, json={"provider": "mock", "phone_number_id": self.phone_number_id})
        assert r.status_code == 200, r.text

    def staff(self, role: str, name: str = "Staff Member") -> dict[str, str]:
        """Create a staff user with a role directly (activation flow is tested separately)."""
        from app.core.permissions import RoleName
        from app.core.security import hash_password
        from app.models import User
        from app.services.rbac import get_system_role

        email = f"{role.lower()}-{uuid.uuid4().hex[:6]}@staff.example.com"
        with SessionLocal() as db:
            u = User(
                organization_id=uuid.UUID(self.org_id),
                email=email,
                password_hash=hash_password(PASSWORD),
                full_name=name,
                role_id=get_system_role(db, RoleName(role)).id,
                is_active=True,
                is_verified=True,
            )
            db.add(u)
            db.commit()
            uid = str(u.id)
        r = self.api.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['access_token']}", "X-User-Id": uid}

    def client(self, name: str = "Rahul Mehta", phone: str | None = None, **kw: Any) -> dict[str, Any]:
        phone = phone or f"98{uuid.uuid4().int % 10**8:08d}"
        body = {"name": name, "phone": phone, "whatsapp_opt_in": True, **kw}
        r = self.api.post("/api/v1/clients", headers=self.h, json=body)
        assert r.status_code == 201, r.text
        return r.json()

    def upload(
        self,
        client_id: str,
        *,
        name: str = "ITR_Ack.pdf",
        content: bytes | None = None,
        document_type: str = "ITR_ACKNOWLEDGEMENT",
        fy: str = "2025-26",
        headers: dict[str, str] | None = None,
    ) -> Any:
        return self.api.post(
            "/api/v1/documents",
            headers=headers or self.h,
            files={"file": (name, content or make_pdf(), "application/pdf")},
            data={"client_id": client_id, "document_type": document_type, "financial_year": fy},
        )

    def portal_login(self, phone: str) -> dict[str, str]:
        r = self.api.post("/api/v1/portal/auth/request-otp", json={"org_slug": self.slug, "phone": phone})
        assert r.status_code == 200, r.text
        code = r.json()["dev_otp"]
        assert code, "dev OTP should be returned in test/mock mode"
        r = self.api.post("/api/v1/portal/auth/verify-otp", json={"org_slug": self.slug, "phone": phone, "code": code})
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    def inbound(
        self,
        phone: str,
        text_: str | None = None,
        *,
        media: tuple[bytes, str, str] | None = None,
        msg_id: str | None = None,
        signed: bool = True,
    ) -> Any:
        return send_webhook(self.api, self.phone_number_id, "91" + phone[-10:], text_, media=media, msg_id=msg_id, signed=signed)


def send_webhook(
    api: TestClient,
    pnid: str,
    wa_id: str,
    text_: str | None,
    *,
    media: tuple[bytes, str, str] | None = None,
    msg_id: str | None = None,
    signed: bool = True,
) -> Any:
    import json

    from app.integrations.whatsapp.base import sign_meta_payload
    from app.services.whatsapp_webhook import build_simulated_payload

    raw = build_simulated_payload(pnid, wa_id, text=text_, profile_name="Client", media=media, caption=None)
    if msg_id:
        data = json.loads(raw)
        data["entry"][0]["changes"][0]["value"]["messages"][0]["id"] = msg_id
        raw = json.dumps(data).encode()
    headers = {"Content-Type": "application/json"}
    if signed:
        headers["X-Hub-Signature-256"] = sign_meta_payload("test-app-secret", raw)
    return api.post("/api/v1/webhooks/whatsapp", content=raw, headers=headers)


def status_webhook(api: TestClient, pnid: str, provider_message_id: str, status: str) -> Any:
    import json
    import time

    from app.integrations.whatsapp.base import sign_meta_payload

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "x",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "metadata": {"phone_number_id": pnid},
                            "statuses": [
                                {"id": provider_message_id, "status": status, "timestamp": str(int(time.time())), "recipient_id": "x"}
                            ],
                        },
                    }
                ],
            }
        ],
    }
    raw = json.dumps(payload).encode()
    return api.post(
        "/api/v1/webhooks/whatsapp",
        content=raw,
        headers={"Content-Type": "application/json", "X-Hub-Signature-256": sign_meta_payload("test-app-secret", raw)},
    )


def last_outbound(db: Any, org_id: str, contains: str | None = None) -> Any:
    from app.models import Message

    db.expire_all()
    stmt = select(Message).where(Message.organization_id == uuid.UUID(org_id), Message.direction == "OUTBOUND")
    msgs = db.execute(stmt.order_by(Message.created_at.desc())).scalars().all()
    if contains:
        msgs = [m for m in msgs if contains in (m.body or "")]
    return msgs[0] if msgs else None


@pytest.fixture
def firm(api: TestClient) -> Firm:
    return Firm(api, "Alpha CA")


@pytest.fixture
def other_firm(api: TestClient) -> Firm:
    return Firm(api, "Beta CA")

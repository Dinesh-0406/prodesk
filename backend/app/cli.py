"""ProDesk management CLI.

python -m app.cli seed                 # demo data (fake), idempotent
python -m app.cli create-superadmin EMAIL PASSWORD
python -m app.cli sync-rbac
python -m app.cli run-reminders
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.core.config import settings
from app.core.context import Principal
from app.core.logging import configure_logging
from app.core.permissions import RoleName
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import Organization, User, WhatsAppAccount
from app.workers import dispatch as _dispatch  # noqa: F401

DEMO_SLUG = "sharma-associates"
DEMO_PASSWORD = "Demo@12345"


def make_pdf(text: str) -> bytes:
    """Build a tiny valid single-page PDF containing `text` (for demo documents)."""
    safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    lines = safe.split("\n")
    content = "BT /F1 14 Tf 72 760 Td 18 TL " + " ".join(f"({ln}) Tj T*" for ln in lines) + " ET"
    objs = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(content)} >>\nstream\n{content}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for i, o in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{o}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return out


def _principal(user: User) -> Principal:
    from app.services.rbac import user_permissions

    return Principal(
        kind="staff",
        organization_id=user.organization_id,
        user_id=user.id,
        role=user.role.name,
        permissions=user_permissions(user),
        ip="127.0.0.1",
    )


def seed() -> None:
    from app.workers.celery_app import celery_app

    celery_app.conf.task_always_eager = True  # seed completes without a running worker
    from app.models.enums import ClientType, ComplianceCategory, ComplianceSource, DocumentType, ServiceType, TaskPriority, TaskStatus
    from app.schemas.billing import InvoiceCreate, InvoiceItemIn
    from app.schemas.client import ClientCreate
    from app.schemas.work import ComplianceEventIn, DocumentRequestCreate, RequestItemIn, TaskCreate
    from app.services import clients, document_requests, documents, invoices, rbac, tasks, templates
    from app.services import misc as misc_svc
    from app.services import whatsapp_webhook as wh

    db = SessionLocal()
    try:
        rbac.sync_system_roles(db)
        db.commit()
        if db.execute(select(Organization).where(Organization.slug == DEMO_SLUG)).scalar_one_or_none():
            print("Demo data already present — nothing to do.")
            return
        org = Organization(
            name="Sharma & Associates (Demo)",
            slug=DEMO_SLUG,
            email="office@demo.example.com",
            phone="+919800000001",
            address="101 Demo Chambers, MG Road, Pune 411001",
            onboarding_step="READY",
            settings={
                "faqs": [
                    {
                        "question": "What are your office timings?",
                        "keywords": ["timing", "timings", "hours", "open"],
                        "answer": "Our office is open Monday to Saturday, 9:30 AM to 6:30 PM.",
                    },
                    {
                        "question": "What is your office address?",
                        "keywords": ["address", "location", "office"],
                        "answer": "101 Demo Chambers, MG Road, Pune 411001.",
                    },
                ]
            },
        )
        db.add(org)
        db.flush()
        staff: dict[str, User] = {}
        for key, name, role in [
            ("admin", "Anita Sharma", RoleName.FIRM_ADMIN),
            ("partner", "Rakesh Sharma", RoleName.PARTNER),
            ("manager", "Meera Iyer", RoleName.MANAGER),
            ("employee", "Vikram Joshi", RoleName.EMPLOYEE),
            ("employee2", "Priya Nair", RoleName.EMPLOYEE),
        ]:
            u = User(
                organization_id=org.id,
                email=f"{key}@demo.example.com",
                password_hash=hash_password(DEMO_PASSWORD),
                full_name=name,
                role_id=rbac.get_system_role(db, role).id,
                is_active=True,
                is_verified=True,
            )
            db.add(u)
            staff[key] = u
        db.flush()
        for u in staff.values():
            db.refresh(u)
        db.add(
            WhatsAppAccount(
                organization_id=org.id,
                provider="mock",
                display_phone_number="+91 98000 00001",
                phone_number_id="mock-phone-number-id",
                business_account_id="mock-waba",
                status="ACTIVE",
            )
        )
        templates.ensure_default_templates(db, org.id)
        db.commit()
        admin = _principal(staff["admin"])

        demo_clients = [
            ("Rahul Mehta", "9876500001", ClientType.INDIVIDUAL, "ABCPM1234K", None, "employee"),
            ("Sunita Verma", "9876500002", ClientType.INDIVIDUAL, "ABCPV2345L", None, "employee"),
            ("Mehta Textiles LLP", "9876500003", ClientType.LLP, "AAKFM3456M", "27AAKFM3456M1Z5", "employee"),
            ("Kumar Traders", "9876500004", ClientType.PROPRIETORSHIP, "ABCPK4567N", "27ABCPK4567N1Z2", "employee2"),
            ("Greenleaf Foods Pvt Ltd", "9876500005", ClientType.COMPANY, "AABCG5678P", "27AABCG5678P1Z9", "employee2"),
            ("Joshi Family Trust", "9876500006", ClientType.TRUST, "AAATJ6789Q", None, "manager"),
            ("Arjun Rao", "9876500007", ClientType.INDIVIDUAL, "ABCPR7890R", None, None),
            ("Patel & Sons", "9876500008", ClientType.PARTNERSHIP, "AAFFP8901S", "24AAFFP8901S1Z4", "manager"),
        ]
        cl = {}
        for name, phone, ctype, pan, gstin, owner in demo_clients:
            c = clients.create_client(
                db,
                admin,
                ClientCreate(
                    name=name,
                    phone=phone,
                    email=f"{name.split()[0].lower()}@example.com",
                    client_type=ctype,
                    pan=pan,
                    gstin=gstin,
                    address="Pune, Maharashtra",
                    assigned_employee_id=staff[owner].id if owner else None,
                    whatsapp_opt_in=True,
                ),
            )
            cl[name] = c
        today = date.today()
        fy_start = today.year if today.month >= 4 else today.year - 1
        cur_fy = f"{fy_start}-{str(fy_start + 1)[-2:]}"
        last_fy = f"{fy_start - 1}-{str(fy_start)[-2:]}"

        t1 = tasks.create_task(
            db,
            admin,
            TaskCreate(
                client_id=cl["Rahul Mehta"].id,
                title=f"ITR filing FY {last_fy}",
                service_type=ServiceType.ITR,
                financial_year=last_fy,
                priority=TaskPriority.HIGH,
                status=TaskStatus.UNDER_REVIEW,
                due_date=today + timedelta(days=5),
                assigned_employee_id=staff["employee"].id,
            ),
        )
        tasks.create_task(
            db,
            admin,
            TaskCreate(
                client_id=cl["Sunita Verma"].id,
                title=f"ITR filing FY {last_fy}",
                service_type=ServiceType.ITR,
                financial_year=last_fy,
                status=TaskStatus.DOCUMENTS_PENDING,
                due_date=today - timedelta(days=3),
                assigned_employee_id=staff["employee"].id,
            ),
        )
        tasks.create_task(
            db,
            admin,
            TaskCreate(
                client_id=cl["Mehta Textiles LLP"].id,
                title="GSTR-3B monthly return",
                service_type=ServiceType.GST,
                status=TaskStatus.WORK_IN_PROGRESS,
                due_date=today + timedelta(days=2),
                assigned_employee_id=staff["employee"].id,
            ),
        )
        tasks.create_task(
            db,
            admin,
            TaskCreate(
                client_id=cl["Greenleaf Foods Pvt Ltd"].id,
                title=f"Statutory audit FY {last_fy}",
                service_type=ServiceType.AUDIT,
                financial_year=last_fy,
                priority=TaskPriority.URGENT,
                status=TaskStatus.WORK_IN_PROGRESS,
                due_date=today + timedelta(days=12),
                assigned_employee_id=staff["employee2"].id,
            ),
        )
        tasks.create_task(
            db,
            admin,
            TaskCreate(
                client_id=cl["Kumar Traders"].id,
                title="TDS return Q2",
                service_type=ServiceType.TDS,
                status=TaskStatus.NEW_REQUEST,
                due_date=today,
                assigned_employee_id=staff["employee2"].id,
            ),
        )
        done = tasks.create_task(
            db,
            admin,
            TaskCreate(
                client_id=cl["Arjun Rao"].id,
                title=f"ITR filing FY {last_fy}",
                service_type=ServiceType.ITR,
                financial_year=last_fy,
                status=TaskStatus.NEW_REQUEST,
            ),
        )
        from app.schemas.work import TaskUpdate

        tasks.update_task(db, admin, done.id, TaskUpdate(status=TaskStatus.FILED, filing_reference="DEMO-ACK-000123"))

        # Documents: approved + delivered for Rahul; one awaiting review
        d1 = documents.upload_document(
            db,
            admin,
            client_id=cl["Rahul Mehta"].id,
            file_name=f"BalanceSheet_FY{last_fy}.pdf",
            content=make_pdf(f"DEMO Balance Sheet\nRahul Mehta\nFY {last_fy}\nFake data for demo"),
            document_type=DocumentType.BALANCE_SHEET,
            financial_year=last_fy,
        )
        documents.approve_document(db, admin, d1.id, note="Reviewed", deliver=True)
        d2 = documents.upload_document(
            db,
            admin,
            client_id=cl["Rahul Mehta"].id,
            file_name=f"ITR_Computation_FY{last_fy}.pdf",
            content=make_pdf(f"DEMO ITR Computation\nFY {last_fy}"),
            document_type=DocumentType.ITR_COMPUTATION,
            financial_year=last_fy,
            task_id=t1.id,
        )
        documents.submit_for_review(db, admin, d2.id)
        d3 = documents.upload_document(
            db,
            admin,
            client_id=cl["Arjun Rao"].id,
            file_name=f"ITR-V_Acknowledgement_FY{last_fy}.pdf",
            content=make_pdf(f"DEMO ITR-V Acknowledgement\nArjun Rao\nAssessment Year {cur_fy}"),
            document_type=DocumentType.ITR_ACKNOWLEDGEMENT,
            financial_year=last_fy,
        )
        documents.approve_document(db, admin, d3.id, deliver=True)
        documents.upload_document(
            db,
            admin,
            client_id=cl["Greenleaf Foods Pvt Ltd"].id,
            file_name="Draft_Audit_Report.pdf",
            content=make_pdf("DEMO Draft Audit Report"),
            document_type=DocumentType.AUDIT_REPORT,
            financial_year=last_fy,
        )

        document_requests.create_request(
            db,
            admin,
            DocumentRequestCreate(
                client_id=cl["Sunita Verma"].id,
                title=f"ITR filing FY {last_fy}",
                due_date=today + timedelta(days=7),
                instructions="Please share clear scans or PDFs.",
                items=[
                    RequestItemIn(name="Bank Statement", document_type="BANK_STATEMENT"),
                    RequestItemIn(name="Form 16", document_type="TDS_DOCUMENT"),
                    RequestItemIn(name="Capital Gains Statement"),
                    RequestItemIn(name="Previous ITR"),
                ],
            ),
        )
        document_requests.create_request(
            db,
            admin,
            DocumentRequestCreate(
                client_id=cl["Mehta Textiles LLP"].id,
                title="GST return — purchase invoices",
                due_date=today - timedelta(days=2),
                items=[RequestItemIn(name="Purchase invoices"), RequestItemIn(name="Bank Statement", document_type="BANK_STATEMENT")],
            ),
        )

        inv1 = invoices.create_invoice(
            db,
            admin,
            InvoiceCreate(
                client_id=cl["Rahul Mehta"].id,
                items=[
                    InvoiceItemIn(
                        description=f"ITR filing FY {last_fy}", sac_code="998231", unit_price=Decimal("3500"), tax_rate=Decimal("18")
                    )
                ],
            ),
        )
        invoices.send_invoice(db, admin, inv1.id)
        inv2 = invoices.create_invoice(
            db,
            admin,
            InvoiceCreate(
                client_id=cl["Greenleaf Foods Pvt Ltd"].id,
                issue_date=today - timedelta(days=30),
                due_date=today - timedelta(days=5),
                items=[
                    InvoiceItemIn(description="Statutory audit fee (part 1)", sac_code="998221", unit_price=Decimal("45000")),
                    InvoiceItemIn(description="Out-of-pocket expenses", unit_price=Decimal("2500"), tax_rate=Decimal("0")),
                ],
            ),
        )
        invoices.send_invoice(db, admin, inv2.id)
        invoices.mark_overdue(db)
        invoices.create_invoice(
            db,
            admin,
            InvoiceCreate(
                client_id=cl["Kumar Traders"].id,
                items=[InvoiceItemIn(description="GST compliance — quarterly", unit_price=Decimal("6000"))],
            ),
        )

        misc_svc.create_compliance(
            db,
            admin,
            ComplianceEventIn(
                category=ComplianceCategory.CUSTOM,
                title="Demo: internal year-end review meeting (example event, not a statutory date)",
                due_date=today + timedelta(days=10),
                source=ComplianceSource.ADMIN_CONFIGURED,
            ),
        )

        # Conversations through the real webhook pipeline (mock signature)
        acc = db.execute(select(WhatsAppAccount).where(WhatsAppAccount.organization_id == org.id)).scalar_one()
        for phone, text in [
            ("919876500001", "Mera ITR status kya hai?"),
            ("919876500001", "Mujhe pichle saal ki balance sheet bhejo"),
            ("919876500002", "Mere kaunse documents pending hain?"),
            ("919876500005", "Mera payment kitna pending hai?"),
            ("919876500004", "CA se baat karni hai"),
        ]:
            raw = wh.build_simulated_payload(acc.phone_number_id, phone, text=text, profile_name=None, media=None, caption=None)
            import json

            for eid in wh.ingest(db, json.loads(raw)):
                wh.process_event(db, eid)
        su_email = "superadmin@example.com"
        if not db.execute(select(User).where(User.email == su_email)).scalar_one_or_none():
            db.add(
                User(
                    organization_id=None,
                    email=su_email,
                    password_hash=hash_password(DEMO_PASSWORD),
                    full_name="Platform Admin",
                    role_id=rbac.get_system_role(db, RoleName.SUPER_ADMIN).id,
                    is_active=True,
                    is_verified=True,
                )
            )
        db.commit()
        print("Seeded demo organization:", org.name)
        print(f"  Staff logins (password for all: {DEMO_PASSWORD}):")
        for k in staff:
            print(f"    {k}@demo.example.com")
        print(f"  Client portal: org slug '{DEMO_SLUG}', phone 9876500001 (OTP shown in dev mode)")
    finally:
        db.close()


def create_superadmin(email: str, password: str) -> None:
    from app.core.security import validate_password_strength
    from app.services import rbac

    validate_password_strength(password)
    with SessionLocal() as db:
        rbac.sync_system_roles(db)
        if db.execute(select(User).where(User.email == email.lower())).scalar_one_or_none():
            print("User already exists")
            return
        db.add(
            User(
                organization_id=None,
                email=email.lower(),
                password_hash=hash_password(password),
                full_name="Platform Admin",
                role_id=rbac.get_system_role(db, RoleName.SUPER_ADMIN).id,
                is_active=True,
                is_verified=True,
            )
        )
        db.commit()
        print("Super admin created")


def main(argv: list[str] | None = None) -> int:
    configure_logging(settings.LOG_LEVEL, json_logs=False)
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("seed")
    sub.add_parser("sync-rbac")
    sub.add_parser("run-reminders")
    p = sub.add_parser("create-superadmin")
    p.add_argument("email")
    p.add_argument("password")
    args = parser.parse_args(argv)
    if args.cmd == "seed":
        if settings.is_production:
            print("Refusing to seed demo data in production", file=sys.stderr)
            return 1
        seed()
    elif args.cmd == "sync-rbac":
        from app.services.rbac import sync_system_roles

        with SessionLocal() as db:
            sync_system_roles(db)
            db.commit()
        print("RBAC synced")
    elif args.cmd == "run-reminders":
        from app.services.reminders import run_reminders

        with SessionLocal() as db:
            print(run_reminders(db))
    elif args.cmd == "create-superadmin":
        create_superadmin(args.email, args.password)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

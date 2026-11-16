"""Security: Organization A → Organization B, Client A → Client B, unauthorized employee."""

from __future__ import annotations

from conftest import Firm


def test_org_a_cannot_access_org_b_resources(api, firm: Firm, other_firm: Firm):
    b_client = other_firm.client("Beta Client", "9811100001")
    b_doc = other_firm.upload(b_client["id"]).json()
    b_task = api.post("/api/v1/tasks", headers=other_firm.h, json={"client_id": b_client["id"], "title": "B task"}).json()
    b_inv = api.post(
        "/api/v1/invoices",
        headers=other_firm.h,
        json={"client_id": b_client["id"], "items": [{"description": "Fee", "unit_price": "1000"}]},
    ).json()

    # Direct object access → 404 (existence not leaked)
    for path in (
        f"/api/v1/clients/{b_client['id']}",
        f"/api/v1/documents/{b_doc['id']}",
        f"/api/v1/tasks/{b_task['id']}",
        f"/api/v1/invoices/{b_inv['id']}",
        f"/api/v1/clients/{b_client['id']}/summary",
    ):
        assert api.get(path, headers=firm.h).status_code == 404, path
    assert api.post(f"/api/v1/documents/{b_doc['id']}/download-url", headers=firm.h).status_code == 404
    assert api.post(f"/api/v1/documents/{b_doc['id']}/approve", headers=firm.h).status_code == 404
    assert api.patch(f"/api/v1/clients/{b_client['id']}", headers=firm.h, json={"name": "Hacked"}).status_code == 404
    # Cannot attach a document/task/invoice to another org's client
    assert firm.upload(b_client["id"]).status_code == 404
    assert api.post("/api/v1/tasks", headers=firm.h, json={"client_id": b_client["id"], "title": "Steal task"}).status_code == 404
    assert (
        api.post(
            "/api/v1/invoices", headers=firm.h, json={"client_id": b_client["id"], "items": [{"description": "x", "unit_price": "1"}]}
        ).status_code
        == 404
    )
    # Lists never include other tenants' data
    assert api.get("/api/v1/clients", headers=firm.h).json()["total"] == 0
    assert api.get("/api/v1/documents", headers=firm.h).json()["total"] == 0
    assert api.get("/api/v1/invoices", headers=firm.h).json()["total"] == 0
    assert api.get("/api/v1/search?q=Beta", headers=firm.h).json()["clients"] == []
    # same phone may exist in both firms independently
    firm.client("Alpha copy", "9811100001")


def test_org_a_cannot_read_org_b_conversations(api, firm: Firm, other_firm: Firm):
    c = other_firm.client("Beta Client", "9811100002")
    other_firm.inbound(c["phone"], "hello")
    convs = api.get("/api/v1/conversations", headers=other_firm.h).json()["items"]
    assert len(convs) == 1
    assert api.get(f"/api/v1/conversations/{convs[0]['id']}/messages", headers=firm.h).status_code == 404
    assert api.post(f"/api/v1/conversations/{convs[0]['id']}/messages", headers=firm.h, json={"body": "x"}).status_code == 404
    assert api.get("/api/v1/conversations", headers=firm.h).json()["total"] == 0


def test_employee_only_sees_assigned_clients(api, firm: Firm):
    emp_h = firm.staff("EMPLOYEE", "Emp One")
    emp_id = emp_h.pop("X-User-Id")
    mine = firm.client("Mine", "9822200001", assigned_employee_id=emp_id)
    other = firm.client("Not Mine", "9822200002")
    doc = firm.upload(other["id"]).json()

    listed = api.get("/api/v1/clients", headers=emp_h).json()
    assert [c["id"] for c in listed["items"]] == [mine["id"]]
    assert api.get(f"/api/v1/clients/{other['id']}", headers=emp_h).status_code == 404
    assert api.get(f"/api/v1/documents/{doc['id']}", headers=emp_h).status_code == 404
    assert api.post(f"/api/v1/documents/{doc['id']}/download-url", headers=emp_h).status_code == 404
    assert api.get(f"/api/v1/clients/{mine['id']}", headers=emp_h).status_code == 200


def test_employee_permission_restrictions(api, firm: Firm):
    emp_h = firm.staff("EMPLOYEE")
    emp_id = emp_h.pop("X-User-Id")
    c = firm.client("Assigned", "9833300001", assigned_employee_id=emp_id)
    doc = firm.upload(c["id"], headers=emp_h).json()
    # Employees can upload but not approve, delete, manage users or settings
    assert api.post(f"/api/v1/documents/{doc['id']}/approve", headers=emp_h).status_code == 403
    assert api.delete(f"/api/v1/documents/{doc['id']}", headers=emp_h).status_code == 403
    assert api.post("/api/v1/users", headers=emp_h, json={"email": "x@y.example.com", "full_name": "X Y"}).status_code == 403
    assert api.patch("/api/v1/organizations/current", headers=emp_h, json={"name": "Nope"}).status_code == 403
    assert api.put("/api/v1/whatsapp/account", headers=emp_h, json={"provider": "mock", "phone_number_id": "zzz"}).status_code == 403
    assert (
        api.post(
            "/api/v1/invoices", headers=emp_h, json={"client_id": c["id"], "items": [{"description": "x", "unit_price": "1"}]}
        ).status_code
        == 403
    )
    assert api.get("/api/v1/audit-logs", headers=emp_h).status_code == 403
    assert api.get("/api/v1/reports/employee-workload", headers=emp_h).status_code == 403


def test_manager_cannot_manage_users_but_can_approve(api, firm: Firm):
    mgr = firm.staff("MANAGER")
    mgr.pop("X-User-Id")
    c = firm.client("Client M", "9844400001")
    doc = firm.upload(c["id"]).json()
    assert api.post("/api/v1/users", headers=mgr, json={"email": "x@y.example.com", "full_name": "X Y"}).status_code == 403
    assert api.post(f"/api/v1/documents/{doc['id']}/approve", headers=mgr, json={"deliver": False}).status_code == 200


def test_role_change_invalidates_existing_session(api, firm: Firm):
    h = firm.staff("MANAGER")
    uid = h.pop("X-User-Id")
    assert api.get("/api/v1/clients", headers=h).status_code == 200
    r = api.patch(f"/api/v1/users/{uid}", headers=firm.h, json={"role": "EMPLOYEE"})
    assert r.status_code == 200 and r.json()["role_name"] == "EMPLOYEE"
    assert api.get("/api/v1/clients", headers=h).status_code == 401
    from app.services.audit import AuditAction

    logs = api.get("/api/v1/audit-logs", headers=firm.h, params={"action": AuditAction.USER_PERMISSION_CHANGED}).json()
    assert logs["total"] == 1 and logs["items"][0]["metadata"] == {"from": "MANAGER", "to": "EMPLOYEE"}


def test_client_token_cannot_use_staff_api(api, firm: Firm):
    c = firm.client("Portal Client", "9855500001")
    ph = firm.portal_login(c["phone"])
    assert api.get("/api/v1/clients", headers=ph).status_code == 403
    assert api.get(f"/api/v1/documents?client_id={c['id']}", headers=ph).status_code == 403
    assert api.get("/api/v1/portal/me", headers=firm.h).status_code == 403


def test_super_admin_has_no_tenant_data_access(api, firm: Firm):
    from app.cli import create_superadmin

    create_superadmin("root@platform.example.com", "R00t-Password!")
    r = api.post("/api/v1/auth/login", json={"email": "root@platform.example.com", "password": "R00t-Password!"})
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert any(o["id"] == firm.org_id for o in api.get("/api/v1/organizations", headers=h).json())
    assert api.get("/api/v1/clients", headers=h).status_code == 403
    assert api.get("/api/v1/organizations", headers=firm.h).status_code == 403

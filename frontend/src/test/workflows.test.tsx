import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { ClientFormModal } from "../features/clients/ClientForm";
import { UploadDocumentModal } from "../features/documents/UploadDocumentModal";
import { InvoiceFormModal, computeTotals } from "../features/invoices/InvoiceFormModal";
import { TaskFormModal } from "../features/tasks/TaskFormModal";
import { AppLayout } from "../layouts/AppLayout";
import { LoginPage } from "../pages/auth/AuthPages";
import { ClientsPage } from "../pages/ClientsPage";
import { DocumentDetailPage } from "../pages/DocumentDetailPage";
import { PortalLinkPage, PortalLoginPage } from "../pages/portal/PortalAuth";
import { WhatsAppPage } from "../pages/WhatsAppPage";
import { ADMIN_ME, EMPLOYEE_ME, mockApi, page, renderApp } from "./utils";

const client = {
  id: "c1", name: "Rahul Mehta", phone: "+919876543210", email: null, address: null, client_type: "INDIVIDUAL", pan: "ABCPM1234K", gstin: null,
  assigned_employee_id: null, assigned_employee: null, status: "ACTIVE", notes: null, whatsapp_opt_in: true, whatsapp_opt_out_at: null,
  reminders_opt_out: false, created_at: "2026-11-01T10:00:00Z", updated_at: "2026-11-01T10:00:00Z",
};

describe("Login", () => {
  it("signs in and loads the user", async () => {
    const calls = mockApi({
      "POST /auth/refresh": new Response("{}", { status: 401 }),
      "POST /auth/login": { access_token: "tok", refresh_token: "r", expires_at: "x" },
      "GET /auth/me": ADMIN_ME,
    });
    renderApp(<LoginPage />, { path: "/login", route: "/login", staff: false });
    await userEvent.type(await screen.findByLabelText("Email"), "admin@firm.example.com");
    await userEvent.type(screen.getByLabelText("Password"), "Secret-Pass-1");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await screen.findByText("other route");
    expect(calls.find((c) => c.path === "/auth/login")?.body).toEqual({ email: "admin@firm.example.com", password: "Secret-Pass-1" });
  });

  it("shows the server error on bad credentials", async () => {
    mockApi({
      "POST /auth/refresh": new Response("{}", { status: 401 }),
      "POST /auth/login": new Response(JSON.stringify({ error: { code: "INVALID_CREDENTIALS", message: "Invalid email or password" } }), { status: 401 }),
    });
    renderApp(<LoginPage />, { path: "/login", route: "/login", staff: false });
    await userEvent.type(await screen.findByLabelText("Email"), "a@b.example.com");
    await userEvent.type(screen.getByLabelText("Password"), "nope");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid email or password");
  });
});

describe("Clients", () => {
  it("searches clients server-side", async () => {
    const calls = mockApi({
      "GET /auth/me": ADMIN_ME, "GET /users": [],
      "GET /clients": (url: URL) => page(url.searchParams.get("q") === "Rahul" ? [client] : []),
    });
    renderApp(<ClientsPage />);
    await userEvent.type(await screen.findByLabelText("Search clients"), "Rahul");
    expect(await screen.findByText("Rahul Mehta")).toBeInTheDocument();
    expect(calls.some((c) => c.path === "/clients" && c.url.searchParams.get("q") === "Rahul")).toBe(true);
  });

  it("creates a client with WhatsApp consent", async () => {
    const calls = mockApi({ "GET /auth/me": ADMIN_ME, "GET /users": [], "POST /clients": client });
    renderApp(<ClientFormModal open onClose={() => undefined} />);
    await userEvent.type(await screen.findByLabelText("Client name"), "Rahul Mehta");
    await userEvent.type(screen.getByLabelText("Mobile (WhatsApp)"), "9876543210");
    await userEvent.type(screen.getByLabelText("PAN"), "abcpm1234k");
    await userEvent.click(screen.getByRole("button", { name: "Save client" }));
    await waitFor(() => expect(calls.find((c) => c.method === "POST" && c.path === "/clients")).toBeTruthy());
    const body = calls.find((c) => c.path === "/clients" && c.method === "POST")!.body as Record<string, unknown>;
    expect(body).toMatchObject({ name: "Rahul Mehta", phone: "9876543210", pan: "ABCPM1234K", whatsapp_opt_in: true, email: null });
  });
});

describe("Documents", () => {
  it("uploads a document as multipart form data", async () => {
    const calls = mockApi({ "GET /auth/me": ADMIN_ME, "POST /documents": { id: "d1", file_name: "itr.pdf" } });
    renderApp(<UploadDocumentModal open clientId="c1" onClose={() => undefined} />);
    const file = new File(["%PDF-1.4"], "itr.pdf", { type: "application/pdf" });
    await userEvent.upload(await screen.findByTestId("file-input"), file);
    await userEvent.click(screen.getByRole("button", { name: "Upload" }));
    await waitFor(() => expect(calls.find((c) => c.method === "POST" && c.path === "/documents")).toBeTruthy());
    const form = calls.find((c) => c.path === "/documents")!.body as FormData;
    expect(form.get("client_id")).toBe("c1");
    expect(form.get("document_type")).toBe("ITR_ACKNOWLEDGEMENT");
    expect((form.get("file") as File).name).toBe("itr.pdf");
  });

  it("approves a document and triggers WhatsApp delivery", async () => {
    const doc = {
      id: "d1", client_id: "c1", client: { id: "c1", name: "Rahul Mehta" }, task_id: null, uploaded_by: "u1", source: "STAFF", file_name: "ITR-V.pdf",
      mime_type: "application/pdf", file_size: 2048, document_type: "ITR_ACKNOWLEDGEMENT", financial_year: "2025-26", assessment_year: null,
      description: null, version: 1, status: "UNDER_REVIEW", approved_version_id: null, created_at: "2026-11-01T10:00:00Z", updated_at: "2026-11-01T10:00:00Z",
      versions: [{ id: "v1", version_number: 1, file_name: "ITR-V.pdf", mime_type: "application/pdf", file_size: 2048, checksum_sha256: "a".repeat(64), status: "UPLOADED", uploaded_by: "u1", reviewed_by: null, reviewed_at: null, review_note: null, created_at: "2026-11-01T10:00:00Z" }],
      deliveries: [], access_history: [], extracted_metadata: {},
    };
    const calls = mockApi({ "GET /auth/me": ADMIN_ME, "GET /documents/d1": doc, "POST /documents/d1/approve": { ...doc, status: "APPROVED" } });
    renderApp(<DocumentDetailPage />, { path: "/documents/:id", route: "/documents/d1" });
    await userEvent.click(await screen.findByRole("button", { name: /Approve & send on WhatsApp/ }));
    await waitFor(() => expect(calls.find((c) => c.path === "/documents/d1/approve")?.body).toEqual({ deliver: true }));
  });
});

describe("Tasks", () => {
  it("creates a task for a client", async () => {
    const calls = mockApi({ "GET /auth/me": ADMIN_ME, "GET /users": [], "POST /tasks": { id: "t1" } });
    renderApp(<TaskFormModal open clientId="c1" onClose={() => undefined} />);
    await userEvent.type(await screen.findByLabelText("Title"), "ITR filing FY 2025-26");
    await userEvent.type(screen.getByLabelText("Due date"), "2026-12-31");
    await userEvent.click(screen.getByRole("button", { name: "Create task" }));
    await waitFor(() => expect(calls.find((c) => c.path === "/tasks" && c.method === "POST")).toBeTruthy());
    expect(calls.find((c) => c.path === "/tasks")!.body).toMatchObject({ client_id: "c1", title: "ITR filing FY 2025-26", service_type: "ITR", due_date: "2026-12-31" });
  });
});

describe("Invoices", () => {
  it("computes GST totals", () => {
    expect(computeTotals([{ description: "ITR", sac_code: "", quantity: "1", unit_price: "3500", tax_rate: "18" },
      { description: "Exp", sac_code: "", quantity: "2", unit_price: "100.50", tax_rate: "0" }])).toEqual({ subtotal: 3701, tax: 630, total: 4331 });
  });

  it("shows live totals in the invoice form", async () => {
    mockApi({ "GET /auth/me": ADMIN_ME });
    renderApp(<InvoiceFormModal open clientId="c1" onClose={() => undefined} />);
    await userEvent.type(await screen.findByLabelText("Description"), "Audit fee");
    await userEvent.type(screen.getByLabelText("Rate"), "1000");
    const totals = screen.getByTestId("invoice-totals");
    expect(within(totals).getByText("₹1,180.00")).toBeInTheDocument();
  });
});

describe("WhatsApp inbox", () => {
  it("shows a conversation and sends an agent reply", async () => {
    const conv = { id: "cv1", contact: { id: "k1", wa_id: "919876543210", phone: "+919876543210", profile_name: "Rahul", last_inbound_at: new Date().toISOString() },
      client_id: "c1", client: { id: "c1", name: "Rahul Mehta" }, status: "OPEN", handover_state: "HUMAN_REQUESTED", assigned_agent: null,
      last_message_at: new Date().toISOString(), last_message_preview: "CA se baat karni hai", unread_count: 1, service_window_open: true };
    const calls = mockApi({
      "GET /auth/me": ADMIN_ME,
      "GET /whatsapp/account": { provider: "mock", status: "ACTIVE" },
      "GET /conversations": page([conv]),
      "GET /conversations/cv1": conv,
      "GET /conversations/cv1/messages": page([{ id: "m1", conversation_id: "cv1", direction: "INBOUND", message_type: "TEXT", sender: "CLIENT", body: "CA se baat karni hai", template_key: null, status: "RECEIVED", timestamp: new Date().toISOString(), error: null, error_code: null }]),
      "POST /conversations/cv1/messages": { id: "m2" },
    });
    renderApp(<WhatsAppPage />, { path: "/whatsapp", route: "/whatsapp" });
    expect(await screen.findAllByText("CA se baat karni hai")).not.toHaveLength(0);
    expect(screen.getAllByText("Wants a person").length).toBeGreaterThan(0);
    await userEvent.type(await screen.findByLabelText("Reply"), "Hello, this is your CA");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => expect(calls.find((c) => c.method === "POST" && c.path === "/conversations/cv1/messages")?.body).toEqual({ body: "Hello, this is your CA" }));
  });
});

describe("Permissions", () => {
  it("hides navigation the user's role cannot use", async () => {
    mockApi({ "GET /auth/me": EMPLOYEE_ME, "GET /notifications": [] });
    renderApp(<AppLayout />);
    const nav = await screen.findByRole("navigation", { name: "Main" });
    await within(nav).findByText("Clients");
    expect(within(nav).getByText("WhatsApp")).toBeInTheDocument();
    for (const hidden of ["Settings", "Employees", "Reports"]) expect(within(nav).queryByText(hidden)).toBeNull();
  });

  it("shows admin navigation to firm admins", async () => {
    mockApi({ "GET /auth/me": ADMIN_ME, "GET /notifications": [] });
    renderApp(<AppLayout />);
    const nav = await screen.findByRole("navigation", { name: "Main" });
    expect(await within(nav).findByText("Settings")).toBeInTheDocument();
    expect(within(nav).getByText("Employees")).toBeInTheDocument();
  });
});

describe("Client portal", () => {
  it("logs in with phone + OTP", async () => {
    const calls = mockApi({
      "POST /auth/refresh": new Response("{}", { status: 401 }),
      "POST /portal/auth/request-otp": { message: "Code sent", dev_otp: "123456" },
      "POST /portal/auth/verify-otp": { access_token: "ptok", client_id: "c1", client_name: "Rahul Mehta", organization_name: "Sharma & Associates", expires_at: "x" },
    });
    renderApp(<PortalLoginPage />, { path: "/portal/login", route: "/portal/login", staff: false });
    await userEvent.type(await screen.findByLabelText("Firm code"), "sharma");
    await userEvent.type(screen.getByLabelText("Mobile number"), "9876543210");
    await userEvent.click(screen.getByRole("button", { name: "Send code on WhatsApp" }));
    expect(await screen.findByTestId("dev-otp")).toHaveTextContent("123456");
    await userEvent.type(screen.getByLabelText("6-digit code"), "123456");
    await userEvent.click(screen.getByRole("button", { name: "Verify & continue" }));
    await screen.findByText("other route");
    expect(calls.find((c) => c.path === "/portal/auth/verify-otp")?.body).toEqual({ org_slug: "sharma", phone: "9876543210", code: "123456" });
    expect(sessionStorage.getItem("prodesk.portal.session")).toBe("ptok");
  });

  it("requires OTP before a WhatsApp link can be downloaded", async () => {
    const calls = mockApi({
      "POST /auth/refresh": new Response("{}", { status: 401 }),
      "GET /portal/link/tok123": { organization_name: "Sharma & Associates", org_slug: "sharma", phone_hint: "+91******3210", expires_at: "x" },
    });
    renderApp(<PortalLinkPage />, { path: "/portal/link/:token", route: "/portal/link/tok123", staff: false });
    expect(await screen.findByText("Document from Sharma & Associates")).toBeInTheDocument();
    expect(screen.getByText(/ending 3210/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Download/ })).toBeNull();
    expect(calls.some((c) => c.path.endsWith("/download"))).toBe(false);
  });
});

import { QueryClient } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { vi } from "vitest";
import { Providers } from "../App";
import { tokens } from "../services/api";

export type Handler = (url: URL, init: RequestInit) => unknown | Promise<unknown>;
export interface Call { method: string; path: string; body: unknown; url: URL }

/** Route-table fetch mock: keys are "METHOD /path" (path without /api/v1). */
export function mockApi(routes: Record<string, Handler | unknown>) {
  const calls: Call[] = [];
  const fn = vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = new URL(String(input), "http://localhost");
    const path = url.pathname.replace(/^\/api\/v1/, "");
    const method = (init.method ?? "GET").toUpperCase();
    let body: unknown = init.body;
    if (typeof init.body === "string") body = JSON.parse(init.body);
    calls.push({ method, path, body, url });
    const key = Object.keys(routes).find((k) => {
      const [m, p] = k.split(" ");
      if (m !== method) return false;
      const re = new RegExp("^" + p.replace(/:[^/]+/g, "[^/]+") + "$");
      return re.test(path);
    });
    if (!key) return new Response(JSON.stringify({ error: { code: "NOT_FOUND", message: `No mock for ${method} ${path}` } }), { status: 404 });
    const h = routes[key];
    const result = typeof h === "function" ? await (h as Handler)(url, init) : h;
    if (result instanceof Response) return result;
    return new Response(JSON.stringify(result ?? {}), { status: 200, headers: { "Content-Type": "application/json" } });
  });
  vi.stubGlobal("fetch", fn);
  return calls;
}

export const ADMIN_ME = {
  id: "u1", email: "admin@firm.example.com", full_name: "Anita Sharma", phone: null, organization_id: "o1", organization_name: "Sharma & Associates",
  organization_slug: "sharma", role: "FIRM_ADMIN", is_verified: true,
  permissions: ["CLIENT_VIEW", "CLIENT_VIEW_ALL", "CLIENT_CREATE", "CLIENT_UPDATE", "CLIENT_DELETE", "DOCUMENT_VIEW", "DOCUMENT_UPLOAD", "DOCUMENT_APPROVE",
    "DOCUMENT_DOWNLOAD", "DOCUMENT_SHARE", "TASK_VIEW", "TASK_CREATE", "TASK_ASSIGN", "TASK_UPDATE", "DOCUMENT_REQUEST_CREATE", "DOCUMENT_REQUEST_MANAGE",
    "INVOICE_VIEW", "INVOICE_CREATE", "PAYMENT_VIEW", "WHATSAPP_VIEW", "WHATSAPP_SEND", "WHATSAPP_MANAGE", "USER_MANAGE", "REPORT_VIEW", "SETTINGS_MANAGE"],
};

export const EMPLOYEE_ME = {
  ...ADMIN_ME, id: "u2", full_name: "Vikram Joshi", role: "EMPLOYEE",
  permissions: ["CLIENT_VIEW", "CLIENT_UPDATE", "DOCUMENT_VIEW", "DOCUMENT_UPLOAD", "DOCUMENT_DOWNLOAD", "TASK_VIEW", "TASK_CREATE", "TASK_UPDATE",
    "DOCUMENT_REQUEST_CREATE", "INVOICE_VIEW", "WHATSAPP_VIEW", "WHATSAPP_SEND"],
};

export const page = <T,>(items: T[]) => ({ items, total: items.length, page: 1, page_size: 25 });

export function renderApp(ui: ReactElement, { path = "/", route = "/", staff = true }: { path?: string; route?: string; staff?: boolean } = {}) {
  tokens.setStaff(staff ? "test-token" : null);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <MemoryRouter initialEntries={[route]}>
      <Providers client={client}>
        <Routes>
          <Route path={path} element={ui} />
          <Route path="*" element={<div>other route</div>} />
        </Routes>
      </Providers>
    </MemoryRouter>,
  );
}

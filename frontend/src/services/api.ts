/**
 * Thin fetch wrapper.
 * - Staff access tokens live in memory only; the refresh token is an httpOnly cookie.
 * - Client-portal sessions are short-lived and kept in sessionStorage.
 */
import type { ApiErrorBody } from "../types";
import { handleDemoRequest } from "./demoStore";

const BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? "";

export class ApiError extends Error {
  status: number;
  code: string;
  details?: unknown;
  constructor(status: number, body: Partial<ApiErrorBody> | null) {
    super(body?.error?.message ?? `Request failed (${status})`);
    this.status = status;
    this.code = body?.error?.code ?? "HTTP_ERROR";
    this.details = body?.error?.details;
  }
}

type TokenKind = "staff" | "portal";
let staffToken: string | null = null;
let onAuthLost: (() => void) | null = null;
const PORTAL_KEY = "prodesk.portal.session";

export const tokens = {
  setStaff(t: string | null) {
    staffToken = t;
  },
  getStaff() {
    return staffToken;
  },
  setPortal(t: string | null) {
    if (t) sessionStorage.setItem(PORTAL_KEY, t);
    else sessionStorage.removeItem(PORTAL_KEY);
  },
  getPortal() {
    return sessionStorage.getItem(PORTAL_KEY);
  },
  onAuthLost(cb: () => void) {
    onAuthLost = cb;
  },
};

let refreshing: Promise<string | null> | null = null;

export async function refreshStaffToken(): Promise<string | null> {
  if (!refreshing) {
    refreshing = fetch(`${BASE}/api/v1/auth/refresh`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json", "ngrok-skip-browser-warning": "true" },
    })
      .then(async (r) => (r.ok ? ((await r.json()) as { access_token: string }).access_token : null))
      .catch(() => null)
      .finally(() => {
        setTimeout(() => (refreshing = null), 0);
      });
  }
  const t = await refreshing;
  staffToken = t;
  return t;
}

export interface RequestOptions {
  method?: string;
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined | null>;
  auth?: TokenKind | "none";
  form?: FormData;
  raw?: boolean;
}

function buildUrl(path: string, query?: RequestOptions["query"]): string {
  const qs = new URLSearchParams();
  Object.entries(query ?? {}).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") qs.set(k, String(v));
  });
  const s = qs.toString();
  return `${BASE}/api/v1${path}${s ? `?${s}` : ""}`;
}

export async function request<T>(path: string, opts: RequestOptions = {}, retried = false): Promise<T> {
  const auth = opts.auth ?? "staff";
  const token = auth === "staff" ? staffToken : auth === "portal" ? tokens.getPortal() : null;

  // Check if explicit demo session is active
  const isDemo = typeof window !== "undefined" && (sessionStorage.getItem("prodesk.demo") || token?.startsWith("demo-"));
  if (isDemo) {
    const demoData = handleDemoRequest<T>(path, opts.method ?? "GET");
    if (demoData !== null) return demoData;
  }

  const headers: Record<string, string> = {
    "ngrok-skip-browser-warning": "true",
  };
  if (token) headers.Authorization = `Bearer ${token}`;
  let body: BodyInit | undefined;
  if (opts.form) body = opts.form;
  else if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }

  let res: Response;
  try {
    res = await fetch(buildUrl(path, opts.query), {
      method: opts.method ?? (body ? "POST" : "GET"),
      headers,
      body,
      credentials: "include",
    });
  } catch (err) {
    // If fetch failed completely (e.g. backend not reachable on Vercel)
    const demoData = handleDemoRequest<T>(path, opts.method ?? "GET");
    if (demoData !== null) return demoData;
    throw err;
  }

  if (res.status === 401 && auth === "staff" && !retried && !path.startsWith("/auth/")) {
    const t = await refreshStaffToken();
    if (t) return request<T>(path, opts, true);
    onAuthLost?.();
  }
  if (res.status === 401 && auth === "portal") tokens.setPortal(null);
  if (!res.ok) {
    // If endpoint returned 404 (e.g. static hosting without API backend)
    if (res.status === 404) {
      const demoData = handleDemoRequest<T>(path, opts.method ?? "GET");
      if (demoData !== null) return demoData;
    }
    let parsed: Partial<ApiErrorBody> | null = null;
    try {
      parsed = (await res.json()) as ApiErrorBody;
    } catch {
      parsed = null;
    }
    throw new ApiError(res.status, parsed);
  }
  if (opts.raw) return (await res.blob()) as unknown as T;
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  get: <T>(path: string, query?: RequestOptions["query"], auth?: RequestOptions["auth"]) => request<T>(path, { query, auth }),
  post: <T>(path: string, body?: unknown, auth?: RequestOptions["auth"], query?: RequestOptions["query"]) =>
    request<T>(path, { method: "POST", body, auth, query }),
  put: <T>(path: string, body?: unknown) => request<T>(path, { method: "PUT", body }),
  patch: <T>(path: string, body?: unknown) => request<T>(path, { method: "PATCH", body }),
  del: <T>(path: string) => request<T>(path, { method: "DELETE" }),
  upload: <T>(path: string, form: FormData, auth?: RequestOptions["auth"]) => request<T>(path, { method: "POST", form, auth }),
  blob: (path: string, query?: RequestOptions["query"]) => request<Blob>(path, { query, raw: true }),
};

export function errorMessage(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.code === "VALIDATION_FAILED" && Array.isArray(e.details) && e.details.length) {
      const d = e.details[0] as { loc?: string[]; msg?: string };
      const field = d.loc?.slice(-1)[0];
      return field ? `${field}: ${d.msg}` : (d.msg ?? e.message);
    }
    return e.message;
  }
  return e instanceof Error ? e.message : "Something went wrong";
}

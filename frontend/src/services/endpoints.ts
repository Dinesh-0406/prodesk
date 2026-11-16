import type {
  AIAnswer, Client, ClientSummary, ComplianceEvent, Conversation, Delivery, Doc, DocDetail, DocRequest, Invoice, Me,
  Message, Notification, Organization, Page, Payment, Report, SupportRequest, Task, Template, User, WhatsAppAccount,
} from "../types";
import { api, request } from "./api";

type Q = Record<string, string | number | boolean | undefined | null>;
export interface TokenResponse { access_token: string; refresh_token: string; expires_at: string }

export const authApi = {
  login: (email: string, password: string) => api.post<TokenResponse>("/auth/login", { email, password }, "none"),
  register: (b: { firm_name: string; admin_name: string; email: string; password: string; phone?: string }) =>
    api.post<TokenResponse>("/auth/register", b, "none"),
  me: () => api.get<Me>("/auth/me"),
  logout: () => api.post("/auth/logout", {}),
  requestReset: (email: string) => api.post("/auth/password-reset/request", { email }, "none"),
  confirmReset: (token: string, new_password: string) => api.post("/auth/password-reset/confirm", { token, new_password }, "none"),
  activate: (token: string, password: string) => api.post("/auth/activate", { token, password }, "none"),
  verifyEmail: (token: string) => api.post("/auth/verify-email", { token }, "none"),
};

export const orgApi = {
  current: () => api.get<Organization>("/organizations/current"),
  update: (b: Partial<Record<string, unknown>>) => api.patch<Organization>("/organizations/current", b),
  users: () => api.get<User[]>("/users"),
  invite: (b: { email: string; full_name: string; role: string; phone?: string }) => api.post<User>("/users", b),
  updateUser: (id: string, b: Partial<{ role: string; is_active: boolean; full_name: string }>) => api.patch<User>(`/users/${id}`, b),
};

export const clientApi = {
  list: (q: Q) => api.get<Page<Client>>("/clients", q),
  get: (id: string) => api.get<Client>(`/clients/${id}`),
  summary: (id: string) => api.get<ClientSummary>(`/clients/${id}/summary`),
  timeline: (id: string) => api.get<{ action: string; timestamp: string; actor_type: string; resource: string | null }[]>(`/clients/${id}/timeline`),
  create: (b: Partial<Client>) => api.post<Client>("/clients", b),
  update: (id: string, b: Partial<Client>) => api.patch<Client>(`/clients/${id}`, b),
  archive: (id: string) => api.post<Client>(`/clients/${id}/archive`),
  import: (file: File) => {
    const f = new FormData();
    f.append("file", file);
    return api.upload<{ created: number; skipped: number; errors: { row: number; error: string }[] }>("/clients/import", f);
  },
  sendWelcome: (id: string) => api.post(`/clients/${id}/whatsapp/welcome`),
  export: (id: string) => api.get<Record<string, unknown>>(`/clients/${id}/export`),
};

export interface UploadDocInput {
  file: File;
  client_id: string;
  document_type: string;
  financial_year?: string;
  description?: string;
  task_id?: string;
}

export const documentApi = {
  list: (q: Q) => api.get<Page<Doc>>("/documents", q),
  get: (id: string) => api.get<DocDetail>(`/documents/${id}`),
  upload: (i: UploadDocInput) => {
    const f = new FormData();
    f.append("file", i.file);
    f.append("client_id", i.client_id);
    f.append("document_type", i.document_type);
    if (i.financial_year) f.append("financial_year", i.financial_year);
    if (i.description) f.append("description", i.description);
    if (i.task_id) f.append("task_id", i.task_id);
    return api.upload<Doc>("/documents", f);
  },
  newVersion: (id: string, file: File) => {
    const f = new FormData();
    f.append("file", file);
    return api.upload<Doc>(`/documents/${id}/versions`, f);
  },
  submit: (id: string) => api.post<Doc>(`/documents/${id}/submit`),
  approve: (id: string, b: { note?: string; deliver?: boolean } = {}) => api.post<Doc>(`/documents/${id}/approve`, b),
  reject: (id: string, reason: string) => api.post<Doc>(`/documents/${id}/reject`, { reason }),
  deliver: (id: string, version_id?: string) => api.post<Delivery>(`/documents/${id}/deliver`, { version_id }),
  archive: (id: string) => api.post<Doc>(`/documents/${id}/archive`),
  remove: (id: string) => api.del(`/documents/${id}`),
  downloadUrl: (id: string, opts: { version_id?: string; inline?: boolean } = {}) =>
    api.post<{ url: string; expires_at: string; file_name: string }>(`/documents/${id}/download-url`, undefined, "staff", opts),
};

export const taskApi = {
  list: (q: Q) => api.get<Page<Task>>("/tasks", q),
  buckets: () => api.get<Record<string, number>>("/tasks/buckets"),
  get: (id: string) => api.get<Task>(`/tasks/${id}`),
  create: (b: Record<string, unknown>) => api.post<Task>("/tasks", b),
  update: (id: string, b: Record<string, unknown>) => api.patch<Task>(`/tasks/${id}`, b),
};

export const requestApi = {
  list: (q: Q) => api.get<Page<DocRequest>>("/document-requests", q),
  get: (id: string) => api.get<DocRequest>(`/document-requests/${id}`),
  create: (b: Record<string, unknown>) => api.post<DocRequest>("/document-requests", b),
  markItem: (id: string, itemId: string, received: boolean) =>
    api.post<DocRequest>(`/document-requests/${id}/items/${itemId}`, undefined, "staff", { received }),
  remind: (id: string) => api.post<DocRequest>(`/document-requests/${id}/remind`),
  cancel: (id: string) => api.post<DocRequest>(`/document-requests/${id}/cancel`),
};

export const whatsappApi = {
  account: () => api.get<WhatsAppAccount>("/whatsapp/account"),
  saveAccount: (b: Record<string, unknown>) => api.put<WhatsAppAccount>("/whatsapp/account", b),
  verify: () => api.post<WhatsAppAccount>("/whatsapp/account/verify"),
  templates: () => api.get<Template[]>("/whatsapp/templates"),
  updateTemplate: (id: string, b: Partial<Template>) => api.patch<Template>(`/whatsapp/templates/${id}`, b),
  syncTemplates: () => api.post<Template[]>("/whatsapp/templates/sync"),
  conversations: (q: Q) => api.get<Page<Conversation>>("/conversations", q),
  conversation: (id: string) => api.get<Conversation>(`/conversations/${id}`),
  messages: (id: string) => api.get<Page<Message>>(`/conversations/${id}/messages`),
  reply: (id: string, body: string) => api.post<Message>(`/conversations/${id}/messages`, { body }),
  handover: (id: string, action: string, agent_id?: string) => api.post<Conversation>(`/conversations/${id}/handover`, { action, agent_id }),
  simulate: (b: { phone: string; text?: string; media_base64?: string; media_mime?: string; media_filename?: string }) =>
    api.post<{ status: string }>("/whatsapp/simulate/inbound", b),
};

export const billingApi = {
  invoices: (q: Q) => api.get<Page<Invoice>>("/invoices", q),
  invoice: (id: string) => api.get<Invoice>(`/invoices/${id}`),
  create: (b: Record<string, unknown>) => api.post<Invoice>("/invoices", b),
  send: (id: string) => api.post<Invoice>(`/invoices/${id}/send`),
  cancel: (id: string) => api.post<Invoice>(`/invoices/${id}/cancel`),
  recordPayment: (id: string, b: { amount: string; reference: string; method: string }) => api.post<Payment>(`/invoices/${id}/payments`, b),
  payments: (q: Q) => api.get<Page<Payment>>("/payments", q),
};

export const insightApi = {
  dashboard: () => api.get<Record<string, number | string>>("/reports/dashboard"),
  reports: () => api.get<string[]>("/reports"),
  report: (name: string) => api.get<Report>(`/reports/${name}`),
  reportCsv: (name: string) => request<Blob>(`/reports/${name}/csv`, { raw: true }),
  ask: (question: string) => api.post<AIAnswer>("/ai/assistant", { question }),
  search: (q: string) => api.get<Record<string, { id: string; title: string; subtitle: string }[]>>("/search", { q }),
  notifications: () => api.get<Notification[]>("/notifications"),
  markRead: () => api.post("/notifications/read"),
  compliance: (q: Q = {}) => api.get<ComplianceEvent[]>("/compliance", q),
  createCompliance: (b: Record<string, unknown>) => api.post<ComplianceEvent>("/compliance", b),
  deleteCompliance: (id: string) => api.del(`/compliance/${id}`),
  support: (q: Q = {}) => api.get<Page<SupportRequest>>("/support-requests", q),
  updateSupport: (id: string, b: Record<string, unknown>) => api.patch<SupportRequest>(`/support-requests/${id}`, b),
};

// ---- client portal ----
export interface PortalSession { access_token: string; client_id: string; client_name: string; organization_name: string; expires_at: string }
export interface PortalTask { id: string; title: string; service_type: string; financial_year: string | null; status: string; status_label: string; due_date: string | null; filed_at: string | null }

export const portalApi = {
  requestOtp: (org_slug: string, phone: string) =>
    api.post<{ message: string; dev_otp: string | null }>("/portal/auth/request-otp", { org_slug, phone }, "none"),
  verifyOtp: (org_slug: string, phone: string, code: string) =>
    api.post<PortalSession>("/portal/auth/verify-otp", { org_slug, phone, code }, "none"),
  linkInfo: (token: string) =>
    api.get<{ organization_name: string; org_slug: string; phone_hint: string; expires_at: string }>(`/portal/link/${token}`, undefined, "none"),
  linkDownload: (token: string) => api.post<{ url: string; file_name: string }>(`/portal/link/${token}/download`, undefined, "portal"),
  me: () => api.get<Record<string, unknown> & { name: string; phone: string; organization: { name: string; phone: string | null; email: string | null; address: string | null } }>("/portal/me", undefined, "portal"),
  dashboard: () => api.get<{ documents: number; pending_requests: number; open_invoices: number; outstanding: string; requests: DocRequest[]; tasks: { title: string; status: string }[] }>("/portal/dashboard", undefined, "portal"),
  documents: (q: Q = {}) => api.get<Page<Doc>>("/portal/documents", q, "portal"),
  documentUrl: (id: string) => api.post<{ url: string; file_name: string }>(`/portal/documents/${id}/download-url`, undefined, "portal"),
  requests: () => api.get<Page<DocRequest>>("/portal/document-requests", undefined, "portal"),
  upload: (requestId: string, file: File, itemId?: string) => {
    const f = new FormData();
    f.append("file", file);
    if (itemId) f.append("item_id", itemId);
    return api.upload<DocRequest>(`/portal/document-requests/${requestId}/upload`, f, "portal");
  },
  tasks: () => api.get<PortalTask[]>("/portal/tasks", undefined, "portal"),
  invoices: () => api.get<Page<Invoice>>("/portal/invoices", undefined, "portal"),
  checkout: (id: string) =>
    api.post<{ provider: string; order_id: string; amount_paise: number; currency: string; key_id: string; invoice_number: string; firm_name: string }>(`/portal/invoices/${id}/checkout`, undefined, "portal"),
  mockComplete: (order_id: string, succeed = true) =>
    api.post<{ razorpay_order_id: string; razorpay_payment_id: string; razorpay_signature: string }>("/portal/payments/mock-complete", { order_id, succeed }, "portal"),
  verifyPayment: (b: { razorpay_order_id: string; razorpay_payment_id: string; razorpay_signature: string }) =>
    api.post<Invoice>("/portal/payments/verify", b, "portal"),
  payments: () => api.get<Page<Payment>>("/portal/payments", undefined, "portal"),
  messages: () => api.get<{ direction: string; sender: string; body: string | null; timestamp: string }[]>("/portal/messages", undefined, "portal"),
  support: () => api.get<Page<SupportRequest>>("/portal/support", undefined, "portal"),
  createSupport: (request_type: string, message: string) => api.post<SupportRequest>("/portal/support", { request_type, message }, "portal"),
};

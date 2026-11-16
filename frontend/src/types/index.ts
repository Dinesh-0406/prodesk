export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface ApiErrorBody {
  error: { code: string; message: string; details?: unknown };
  request_id?: string;
}

export interface Me {
  id: string;
  email: string;
  full_name: string;
  phone: string | null;
  organization_id: string | null;
  organization_name: string | null;
  organization_slug: string | null;
  role: string;
  permissions: string[];
  is_verified: boolean;
}

export interface Ref {
  id: string;
  name: string;
}
export interface EmployeeRef {
  id: string;
  full_name: string;
}

export type ClientType = "INDIVIDUAL" | "PROPRIETORSHIP" | "PARTNERSHIP" | "LLP" | "COMPANY" | "TRUST" | "OTHER";

export interface Client {
  id: string;
  name: string;
  phone: string;
  email: string | null;
  address: string | null;
  client_type: ClientType;
  pan: string | null;
  gstin: string | null;
  assigned_employee_id: string | null;
  assigned_employee: EmployeeRef | null;
  status: string;
  notes: string | null;
  whatsapp_opt_in: boolean;
  whatsapp_opt_out_at: string | null;
  reminders_opt_out: boolean;
  created_at: string;
  updated_at: string;
}

export interface ClientSummary {
  client: Client;
  counts: Record<string, number>;
  outstanding_amount: string;
  whatsapp_status: "OPTED_IN" | "OPTED_OUT" | "NOT_OPTED_IN";
  last_message_at: string | null;
  pending_requests: { id: string; title: string; status: string; due_date: string | null; pending_items: string[] }[];
  open_tasks: { id: string; title: string; status: string; service_type: string; due_date: string | null }[];
}

export interface DocumentVersion {
  id: string;
  version_number: number;
  file_name: string;
  mime_type: string;
  file_size: number;
  checksum_sha256: string;
  status: string;
  uploaded_by: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  review_note: string | null;
  created_at: string;
}

export interface Doc {
  id: string;
  client_id: string;
  client: Ref;
  task_id: string | null;
  uploaded_by: string | null;
  source: string;
  file_name: string;
  mime_type: string;
  file_size: number;
  document_type: string;
  financial_year: string | null;
  assessment_year: string | null;
  description: string | null;
  version: number;
  status: string;
  approved_version_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface Delivery {
  id: string;
  version_id: string;
  channel: string;
  status: string;
  sent_at: string | null;
  delivered_at: string | null;
  read_at: string | null;
  downloaded_at: string | null;
  download_count: number;
  expires_at: string;
  error: string | null;
  created_at: string;
}

export interface DocDetail extends Doc {
  versions: DocumentVersion[];
  deliveries: Delivery[];
  access_history: { action: string; actor_type: string; user_id: string | null; client_id: string | null; timestamp: string; ip: string | null; metadata: Record<string, unknown> }[];
  extracted_metadata: Record<string, { suggestion?: { document_type?: string | null; financial_year?: string | null } } | unknown>;
}

export interface Task {
  id: string;
  client_id: string;
  client: Ref;
  assigned_employee_id: string | null;
  assigned_employee: EmployeeRef | null;
  title: string;
  description: string | null;
  service_type: string;
  financial_year: string | null;
  priority: string;
  status: string;
  due_date: string | null;
  completed_at: string | null;
  filed_at: string | null;
  filing_reference: string | null;
  created_at: string;
  updated_at: string;
}

export interface RequestItem {
  id: string;
  name: string;
  document_type: string | null;
  is_required: boolean;
  status: "PENDING" | "RECEIVED";
  document_id: string | null;
  received_at: string | null;
}

export interface DocRequest {
  id: string;
  client_id: string;
  client: Ref;
  task_id: string | null;
  title: string;
  instructions: string | null;
  due_date: string | null;
  status: string;
  reminders_sent: number;
  last_reminder_at: string | null;
  notified_at: string | null;
  completed_at: string | null;
  items: RequestItem[];
  created_at: string;
}

export interface InvoiceItem {
  id: string;
  description: string;
  sac_code: string | null;
  quantity: string;
  unit_price: string;
  tax_rate: string;
  amount: string;
  tax_amount: string;
}

export interface Invoice {
  id: string;
  client_id: string;
  client: Ref;
  invoice_number: string;
  issue_date: string;
  due_date: string;
  subtotal: string;
  tax: string;
  total: string;
  amount_paid: string;
  balance_due: string;
  currency: string;
  status: string;
  notes: string | null;
  sent_at: string | null;
  paid_at: string | null;
  items: InvoiceItem[];
  created_at: string;
}

export interface Payment {
  id: string;
  invoice_id: string;
  client: Ref;
  provider: string;
  provider_payment_id: string;
  amount: string;
  method: string | null;
  status: string;
  paid_at: string;
  verified_via: string;
}

export interface Conversation {
  id: string;
  contact: { id: string; wa_id: string; phone: string | null; profile_name: string | null; last_inbound_at: string | null };
  client_id: string | null;
  client: Ref | null;
  status: string;
  handover_state: string;
  assigned_agent: EmployeeRef | null;
  last_message_at: string | null;
  last_message_preview: string | null;
  unread_count: number;
  service_window_open: boolean;
}

export interface Message {
  id: string;
  conversation_id: string;
  direction: "INBOUND" | "OUTBOUND";
  message_type: string;
  sender: "CLIENT" | "BOT" | "AGENT" | "SYSTEM";
  body: string | null;
  template_key: string | null;
  status: string;
  timestamp: string;
  error: string | null;
  error_code: string | null;
}

export interface User {
  id: string;
  email: string;
  full_name: string;
  phone: string | null;
  role_name: string;
  is_active: boolean;
  is_verified: boolean;
  last_login_at: string | null;
  created_at: string;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  email: string | null;
  phone: string | null;
  address: string | null;
  timezone: string;
  status: string;
  onboarding_step: string;
  has_logo: boolean;
  settings: {
    working_hours: { start: string; end: string; days: number[] };
    notifications: { whatsapp_enabled: boolean; email_enabled: boolean; auto_deliver_on_approval: boolean };
    reminders: { frequency_hours: number; max_reminders: number; quiet_hours_start: string; quiet_hours_end: string; invoice_reminders_enabled: boolean; document_reminders_enabled: boolean };
    invoice: { prefix: string; default_tax_rate: number; payment_terms_days: number; gstin: string; footer: string };
    privacy: { document_retention_days: number; notice_version: string };
    faqs: { question: string; answer: string; keywords: string[] }[];
  };
}

export interface WhatsAppAccount {
  id: string | null;
  provider: "mock" | "meta";
  display_phone_number: string | null;
  phone_number_id: string | null;
  business_account_id: string | null;
  api_version: string | null;
  status: string;
  access_token_set: boolean;
  access_token_hint: string | null;
  app_secret_set: boolean;
  last_error: string | null;
  last_verified_at: string | null;
  webhook_url: string;
  verify_token_configured: boolean;
}

export interface Template {
  id: string;
  key: string;
  name: string;
  language: string;
  category: string;
  status: string;
  body_preview: string;
  variables: string[];
  has_url_button: boolean;
  last_error: string | null;
}

export interface ComplianceEvent {
  id: string;
  category: string;
  title: string;
  description: string | null;
  due_date: string;
  period: string | null;
  source: string;
  source_reference: string | null;
  verified_by: string | null;
  client_id: string | null;
  reminder_days_before: number;
}

export interface SupportRequest {
  id: string;
  client_id: string;
  client: Ref;
  request_type: string;
  message: string | null;
  status: string;
  scheduled_at: string | null;
  created_at: string;
}

export interface Notification {
  id: string;
  type: string;
  title: string;
  body: string | null;
  link: string | null;
  read_at: string | null;
  created_at: string;
}

export interface Report {
  columns: string[];
  rows: Record<string, string | number>[];
}

export interface AIAnswer {
  query: string;
  answer: string;
  columns: string[];
  rows: Record<string, string | number>[];
  disclaimer: string;
}

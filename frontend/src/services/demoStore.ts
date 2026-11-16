/**
 * ProDesk In-Memory Demo Data Store
 * Provides rich, realistic data for CA and Client Portals when running without a live backend.
 */
import type {
  Client,
  ComplianceEvent,
  Conversation,
  Doc,
  DocDetail,
  DocRequest,
  Invoice,
  Me,
  Organization,
  Page,
  Payment,
  Task,
  User,
} from "../types";

export const DEMO_ADMIN: Me = {
  id: "u-admin",
  email: "admin@sharma-ca.example.com",
  full_name: "Anita Sharma, FCA",
  phone: "+91 98000 00001",
  organization_id: "org-sharma",
  organization_name: "Sharma & Associates Chartered Accountants",
  organization_slug: "sharma",
  role: "FIRM_ADMIN",
  is_verified: true,
  permissions: [
    "CLIENT_VIEW",
    "CLIENT_VIEW_ALL",
    "CLIENT_CREATE",
    "CLIENT_UPDATE",
    "CLIENT_DELETE",
    "DOCUMENT_VIEW",
    "DOCUMENT_UPLOAD",
    "DOCUMENT_APPROVE",
    "DOCUMENT_DOWNLOAD",
    "DOCUMENT_SHARE",
    "TASK_VIEW",
    "TASK_CREATE",
    "TASK_ASSIGN",
    "TASK_UPDATE",
    "DOCUMENT_REQUEST_CREATE",
    "DOCUMENT_REQUEST_MANAGE",
    "INVOICE_VIEW",
    "INVOICE_CREATE",
    "PAYMENT_VIEW",
    "WHATSAPP_VIEW",
    "WHATSAPP_SEND",
    "WHATSAPP_MANAGE",
    "USER_MANAGE",
    "REPORT_VIEW",
    "SETTINGS_MANAGE",
  ],
};

export const DEMO_ORG: Organization = {
  id: "org-sharma",
  name: "Sharma & Associates Chartered Accountants",
  slug: "sharma",
  email: "office@sharma-ca.example.com",
  phone: "+91 98000 00001",
  address: "Suite 402, Trade Tower, Senapati Bapat Road, Pune 411016",
  timezone: "Asia/Kolkata",
  status: "ACTIVE",
  onboarding_step: "READY",
  has_logo: false,
  settings: {
    working_hours: { start: "09:30", end: "18:30", days: [1, 2, 3, 4, 5, 6] },
    notifications: {
      whatsapp_enabled: true,
      email_enabled: true,
      auto_deliver_on_approval: true,
    },
    reminders: {
      document_reminders_enabled: true,
      invoice_reminders_enabled: true,
      frequency_hours: 48,
      max_reminders: 3,
      quiet_hours_start: "20:00",
      quiet_hours_end: "09:00",
    },
    invoice: {
      prefix: "INV-2026-",
      default_tax_rate: 18,
      payment_terms_days: 15,
      gstin: "27AAAFS1234F1Z9",
      footer: "Thank you for trusting Sharma & Associates.",
    },
    privacy: {
      document_retention_days: 2920,
      notice_version: "2026.1",
    },
    faqs: [
      {
        question: "What are your office hours?",
        answer: "Our office operates Monday through Saturday, 9:30 AM to 6:30 PM IST.",
        keywords: ["timing", "hours", "office"],
      },
      {
        question: "How can I send my Bank Statements?",
        answer: "You can attach PDF statements directly in this WhatsApp chat or upload via the Client Portal.",
        keywords: ["bank", "statement", "upload"],
      },
    ],
  },
};

export const DEMO_CLIENTS: Client[] = [
  {
    id: "c1",
    name: "Rahul Mehta",
    phone: "+919876543210",
    email: "rahul.mehta@example.com",
    address: "B-12 Woodland Park, Aundh, Pune 411007",
    client_type: "INDIVIDUAL",
    pan: "ABCPM1234K",
    gstin: null,
    assigned_employee_id: "u-emp1",
    assigned_employee: { id: "u-emp1", full_name: "Vikram Joshi" },
    status: "ACTIVE",
    notes: "Salaried professional with equity trading & capital gains.",
    whatsapp_opt_in: true,
    whatsapp_opt_out_at: null,
    reminders_opt_out: false,
    created_at: "2026-01-10T10:00:00Z",
    updated_at: "2026-01-10T10:00:00Z",
  },
  {
    id: "c2",
    name: "Sunita Verma",
    phone: "+919876500002",
    email: "sunita.verma@example.com",
    address: "Flat 401, Sapphire Enclave, Kalyani Nagar, Pune",
    client_type: "INDIVIDUAL",
    pan: "ABCPV2345L",
    gstin: null,
    assigned_employee_id: "u-emp1",
    assigned_employee: { id: "u-emp1", full_name: "Vikram Joshi" },
    status: "ACTIVE",
    notes: "Senior doctor, medical consultancy & clinic receipts.",
    whatsapp_opt_in: true,
    whatsapp_opt_out_at: null,
    reminders_opt_out: false,
    created_at: "2026-01-12T10:00:00Z",
    updated_at: "2026-01-12T10:00:00Z",
  },
  {
    id: "c3",
    name: "Mehta Textiles LLP",
    phone: "+919876500003",
    email: "accounts@mehtatextiles.example.com",
    address: "Plot 45, MIDC Bhosari Industrial Area, Pune 411026",
    client_type: "LLP",
    pan: "AAKFM3456M",
    gstin: "27AAKFM3456M1Z5",
    assigned_employee_id: "u-mgr",
    assigned_employee: { id: "u-mgr", full_name: "Meera Iyer" },
    status: "ACTIVE",
    notes: "Textile manufacturing & exports. Monthly GST & quarterly TDS filing.",
    whatsapp_opt_in: true,
    whatsapp_opt_out_at: null,
    reminders_opt_out: false,
    created_at: "2026-01-15T10:00:00Z",
    updated_at: "2026-01-15T10:00:00Z",
  },
  {
    id: "c4",
    name: "Greenleaf Foods Pvt Ltd",
    phone: "+919876500005",
    email: "finance@greenleaffoods.example.com",
    address: "Survey 12, Baner Pashan Link Road, Pune 411045",
    client_type: "COMPANY",
    pan: "AABCG5678P",
    gstin: "27AABCG5678P1Z9",
    assigned_employee_id: "u-mgr",
    assigned_employee: { id: "u-mgr", full_name: "Meera Iyer" },
    status: "ACTIVE",
    notes: "Packaged foods D2C brand. Statutory audit, ROC compliance & GST.",
    whatsapp_opt_in: true,
    whatsapp_opt_out_at: null,
    reminders_opt_out: false,
    created_at: "2026-02-01T10:00:00Z",
    updated_at: "2026-02-01T10:00:00Z",
  },
  {
    id: "c5",
    name: "Kumar Traders",
    phone: "+919876500004",
    email: "contact@kumartraders.example.com",
    address: "Shop 14, Market Yard, Gultekdi, Pune",
    client_type: "PROPRIETORSHIP",
    pan: "ABCPK4567N",
    gstin: "27ABCPK4567N1Z2",
    assigned_employee_id: "u-emp2",
    assigned_employee: { id: "u-emp2", full_name: "Priya Nair" },
    status: "ACTIVE",
    notes: "Wholesale grain trading. Requires quarterly advance tax review.",
    whatsapp_opt_in: true,
    whatsapp_opt_out_at: null,
    reminders_opt_out: false,
    created_at: "2026-02-10T10:00:00Z",
    updated_at: "2026-02-10T10:00:00Z",
  },
];

export const DEMO_DOCUMENTS: Doc[] = [
  {
    id: "d1",
    client_id: "c1",
    client: { id: "c1", name: "Rahul Mehta" },
    task_id: "t1",
    uploaded_by: "u-admin",
    source: "STAFF",
    file_name: "ITR_V_Acknowledgement_AY2025_26.pdf",
    mime_type: "application/pdf",
    file_size: 148520,
    document_type: "ITR_ACKNOWLEDGEMENT",
    financial_year: "2024-25",
    assessment_year: "2025-26",
    description: "Official verified ITR-V e-filing acknowledgement from Income Tax portal.",
    version: 1,
    status: "APPROVED",
    approved_version_id: "v1",
    created_at: "2026-03-01T14:30:00Z",
    updated_at: "2026-03-01T14:30:00Z",
  },
  {
    id: "d2",
    client_id: "c1",
    client: { id: "c1", name: "Rahul Mehta" },
    task_id: "t1",
    uploaded_by: "u-admin",
    source: "STAFF",
    file_name: "Tax_Computation_Sheet_FY2425.pdf",
    mime_type: "application/pdf",
    file_size: 215400,
    document_type: "COMPUTATION_SHEET",
    financial_year: "2024-25",
    assessment_year: "2025-26",
    description: "Detailed tax computation including 80C deductions and LTCG offsets.",
    version: 1,
    status: "APPROVED",
    approved_version_id: "v2",
    created_at: "2026-03-01T14:32:00Z",
    updated_at: "2026-03-01T14:32:00Z",
  },
  {
    id: "d3",
    client_id: "c3",
    client: { id: "c3", name: "Mehta Textiles LLP" },
    task_id: "t3",
    uploaded_by: "u-mgr",
    source: "STAFF",
    file_name: "GSTR3B_Filing_Jan2026.pdf",
    mime_type: "application/pdf",
    file_size: 198400,
    document_type: "GST_RETURN",
    financial_year: "2025-26",
    assessment_year: null,
    description: "GSTR-3B filed acknowledgement with ARN receipt.",
    version: 1,
    status: "UNDER_REVIEW",
    approved_version_id: null,
    created_at: "2026-02-20T11:00:00Z",
    updated_at: "2026-02-20T11:00:00Z",
  },
];

export const DEMO_DOCUMENT_DETAIL: DocDetail = {
  ...DEMO_DOCUMENTS[0],
  versions: [
    {
      id: "v1",
      version_number: 1,
      file_name: "ITR_V_Acknowledgement_AY2025_26.pdf",
      mime_type: "application/pdf",
      file_size: 148520,
      checksum_sha256: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      status: "APPROVED",
      uploaded_by: "Anita Sharma",
      reviewed_by: "Anita Sharma",
      reviewed_at: "2026-03-01T15:00:00Z",
      review_note: "Verified with IT Portal JSON digest.",
      created_at: "2026-03-01T14:30:00Z",
    },
  ],
  deliveries: [
    {
      id: "del1",
      version_id: "v1",
      channel: "WHATSAPP",
      status: "DELIVERED",
      sent_at: "2026-03-01T15:04:00Z",
      delivered_at: "2026-03-01T15:05:00Z",
      read_at: null,
      downloaded_at: "2026-03-01T15:12:00Z",
      download_count: 1,
      expires_at: "2026-03-08T15:04:00Z",
      error: null,
      created_at: "2026-03-01T15:04:00Z",
    },
  ],
  access_history: [
    {
      action: "DOWNLOAD",
      actor_type: "CLIENT",
      user_id: null,
      client_id: "c1",
      timestamp: "2026-03-01T15:12:00Z",
      ip: "49.36.120.14",
      metadata: {},
    },
  ],
  extracted_metadata: {
    pan: "ABCPM1234K",
    assessment_year: "2025-26",
    tax_payable: "0",
    refund_due: "24,800",
  },
};

export const DEMO_REQUESTS: DocRequest[] = [
  {
    id: "req1",
    client_id: "c1",
    client: { id: "c1", name: "Rahul Mehta" },
    task_id: "t1",
    title: "Bank Statements & Form 16 for ITR",
    instructions: "Please upload 12-month bank statement (HDFC) and Form 16 Part A & B from your employer.",
    due_date: "2026-04-15",
    status: "ACTIVE",
    reminders_sent: 1,
    last_reminder_at: "2026-03-01T09:00:00Z",
    notified_at: "2026-03-01T09:00:00Z",
    completed_at: null,
    items: [
      { id: "i1", name: "Form 16 (Part A & B)", document_type: "FORM_16", is_required: true, status: "RECEIVED", document_id: "d-f16", received_at: "2026-03-01T10:00:00Z" },
      { id: "i2", name: "Bank Statement FY 2025-26 (PDF)", document_type: "BANK_STATEMENT", is_required: true, status: "PENDING", document_id: null, received_at: null },
      { id: "i3", name: "Zerodha Annual P&L Statement", document_type: "OTHER", is_required: false, status: "PENDING", document_id: null, received_at: null },
    ],
    created_at: "2026-03-01T10:00:00Z",
  },
];

export const DEMO_TASKS: Task[] = [
  {
    id: "t1",
    client_id: "c1",
    client: { id: "c1", name: "Rahul Mehta" },
    assigned_employee_id: "u-emp1",
    assigned_employee: { id: "u-emp1", full_name: "Vikram Joshi" },
    title: "ITR Filing FY 2024-25 (AY 2025-26)",
    description: "Tax computation verified. Waiting for client approval on refund computation.",
    service_type: "ITR",
    financial_year: "2024-25",
    priority: "HIGH",
    status: "UNDER_REVIEW",
    due_date: "2026-03-31",
    completed_at: null,
    filed_at: null,
    filing_reference: null,
    created_at: "2026-02-15T10:00:00Z",
    updated_at: "2026-03-01T12:00:00Z",
  },
  {
    id: "t2",
    client_id: "c2",
    client: { id: "c2", name: "Sunita Verma" },
    assigned_employee_id: "u-emp1",
    assigned_employee: { id: "u-emp1", full_name: "Vikram Joshi" },
    title: "Advance Tax Q4 Computation",
    description: "Q4 Advance tax payment installment calculation pending.",
    service_type: "ADVANCE_TAX",
    financial_year: "2025-26",
    priority: "URGENT",
    status: "IN_PROGRESS",
    due_date: "2026-03-15",
    completed_at: null,
    filed_at: null,
    filing_reference: null,
    created_at: "2026-02-20T10:00:00Z",
    updated_at: "2026-03-01T12:00:00Z",
  },
  {
    id: "t3",
    client_id: "c3",
    client: { id: "c3", name: "Mehta Textiles LLP" },
    assigned_employee_id: "u-mgr",
    assigned_employee: { id: "u-mgr", full_name: "Meera Iyer" },
    title: "GSTR-3B Monthly Return Filing",
    description: "Filed on time without late fees.",
    service_type: "GST",
    financial_year: "2025-26",
    priority: "NORMAL",
    status: "COMPLETED",
    due_date: "2026-02-20",
    completed_at: "2026-02-19T16:45:00Z",
    filed_at: "2026-02-19T16:45:00Z",
    filing_reference: "AA2702260192847",
    created_at: "2026-02-01T10:00:00Z",
    updated_at: "2026-02-19T16:45:00Z",
  },
];

export const DEMO_INVOICES: Invoice[] = [
  {
    id: "inv1",
    client_id: "c1",
    client: { id: "c1", name: "Rahul Mehta" },
    invoice_number: "INV-2026-0042",
    issue_date: "2026-02-15",
    due_date: "2026-03-02",
    subtotal: "4500.00",
    tax: "810.00",
    total: "5310.00",
    amount_paid: "0.00",
    balance_due: "5310.00",
    currency: "INR",
    status: "SENT",
    notes: "Professional fee for ITR-2 filing & capital gains computation.",
    sent_at: "2026-02-15T11:00:00Z",
    paid_at: null,
    created_at: "2026-02-15T10:00:00Z",
    items: [
      {
        id: "item1",
        description: "Income Tax Return Filing (ITR-2) with Multiple Form 16s",
        sac_code: "998231",
        quantity: "1",
        unit_price: "3500.00",
        tax_rate: "18",
        tax_amount: "630.00",
        amount: "3500.00",
      },
      {
        id: "item2",
        description: "Equity & Mutual Fund Capital Gains Tax Computation",
        sac_code: "998231",
        quantity: "1",
        unit_price: "1000.00",
        tax_rate: "18",
        tax_amount: "180.00",
        amount: "1000.00",
      },
    ],
  },
  {
    id: "inv2",
    client_id: "c3",
    client: { id: "c3", name: "Mehta Textiles LLP" },
    invoice_number: "INV-2026-0038",
    issue_date: "2026-02-01",
    due_date: "2026-02-15",
    subtotal: "12000.00",
    tax: "2160.00",
    total: "14160.00",
    amount_paid: "14160.00",
    balance_due: "0.00",
    currency: "INR",
    status: "PAID",
    notes: "Monthly retainer for GST compliance & vendor reconciliation.",
    sent_at: "2026-02-01T10:00:00Z",
    paid_at: "2026-02-12T14:20:00Z",
    created_at: "2026-02-01T09:30:00Z",
    items: [
      {
        id: "item3",
        description: "Monthly GST Retainer (GSTR-1, GSTR-3B & 2B Matching)",
        sac_code: "998231",
        quantity: "1",
        unit_price: "12000.00",
        tax_rate: "18",
        tax_amount: "2160.00",
        amount: "12000.00",
      },
    ],
  },
];

export const DEMO_PAYMENTS: Payment[] = [
  {
    id: "p1",
    invoice_id: "inv2",
    client: { id: "c3", name: "Mehta Textiles LLP" },
    amount: "14160.00",
    provider: "RAZORPAY",
    provider_payment_id: "pay_N8h9sKl0912",
    method: "UPI",
    status: "CAPTURED",
    paid_at: "2026-02-12T14:20:00Z",
    verified_via: "WEBHOOK",
  },
];

export const DEMO_CONVERSATIONS: Conversation[] = [
  {
    id: "conv1",
    client_id: "c1",
    client: { id: "c1", name: "Rahul Mehta" },
    contact: {
      id: "cnt1",
      wa_id: "919876543210",
      phone: "+919876543210",
      profile_name: "Rahul Mehta",
      last_inbound_at: "2026-03-01T14:10:00Z",
    },
    status: "OPEN",
    handover_state: "HUMAN_REQUESTED",
    assigned_agent: { id: "u-emp1", full_name: "Vikram Joshi" },
    last_message_at: "2026-03-01T14:10:00Z",
    last_message_preview: "Sir, does the ITR refund get credited directly to my HDFC account?",
    unread_count: 1,
    service_window_open: true,
  },
  {
    id: "conv2",
    client_id: "c3",
    client: { id: "c3", name: "Mehta Textiles LLP" },
    contact: {
      id: "cnt2",
      wa_id: "919876500003",
      phone: "+919876500003",
      profile_name: "Dinesh Mehta",
      last_inbound_at: "2026-02-28T16:00:00Z",
    },
    status: "OPEN",
    handover_state: "BOT",
    assigned_agent: null,
    last_message_at: "2026-02-28T16:00:00Z",
    last_message_preview: "Thank you for the GSTR-3B acknowledgement.",
    unread_count: 0,
    service_window_open: false,
  },
];

export const DEMO_MESSAGES = [
  {
    id: "msg1",
    conversation_id: "conv1",
    direction: "OUTBOUND",
    message_type: "TEMPLATE",
    sender: "SYSTEM",
    body: "Namaste Rahul Mehta ji, your ITR Acknowledgement for AY 2025-26 has been approved and filed by Sharma & Associates. View & download your document securely here: https://prodesk-ca.vercel.app/portal/link/tok123",
    template_key: "document_delivered",
    status: "DELIVERED",
    timestamp: "2026-03-01T14:05:00Z",
    error: null,
    error_code: null,
  },
  {
    id: "msg2",
    conversation_id: "conv1",
    direction: "INBOUND",
    message_type: "TEXT",
    sender: "CLIENT",
    body: "Sir, does the ITR refund get credited directly to my HDFC account?",
    template_key: null,
    status: "RECEIVED",
    timestamp: "2026-03-01T14:10:00Z",
    error: null,
    error_code: null,
  },
];

export const DEMO_COMPLIANCE: ComplianceEvent[] = [
  {
    id: "comp1",
    category: "ADVANCE_TAX",
    title: "4th Installment of Advance Tax FY 2025-26",
    due_date: "2026-03-15",
    description: "Last installment of advance tax (100% of tax liability) for corporate and non-corporate assessees.",
    period: "Q4 FY2526",
    source: "STATUTORY",
    source_reference: "Sec 211 Income Tax Act",
    verified_by: "Anita Sharma",
    client_id: null,
    reminder_days_before: 5,
  },
  {
    id: "comp2",
    category: "GST",
    title: "GSTR-3B Monthly Return (Feb 2026)",
    due_date: "2026-03-20",
    description: "Summary return of outward and inward supplies along with payment of GST liability.",
    period: "Feb 2026",
    source: "STATUTORY",
    source_reference: "Rule 61(5) CGST Rules",
    verified_by: "Anita Sharma",
    client_id: null,
    reminder_days_before: 3,
  },
  {
    id: "comp3",
    category: "TDS",
    title: "TDS Deposit for February 2026",
    due_date: "2026-03-07",
    description: "Deposit of tax deducted at source under Section 192, 194C, 194J, etc.",
    period: "Feb 2026",
    source: "STATUTORY",
    source_reference: "Sec 200(1) Income Tax Act",
    verified_by: "Anita Sharma",
    client_id: null,
    reminder_days_before: 2,
  },
];

export const DEMO_USERS: User[] = [
  {
    id: "u-admin",
    email: "admin@sharma-ca.example.com",
    full_name: "Anita Sharma, FCA",
    phone: null,
    role_name: "FIRM_ADMIN",
    is_active: true,
    is_verified: true,
    last_login_at: "2026-03-01T10:00:00Z",
    created_at: "2026-01-01T00:00:00Z",
  },
  {
    id: "u-mgr",
    email: "meera@sharma-ca.example.com",
    full_name: "Meera Iyer, ACA",
    phone: null,
    role_name: "MANAGER",
    is_active: true,
    is_verified: true,
    last_login_at: "2026-02-28T18:00:00Z",
    created_at: "2026-01-05T00:00:00Z",
  },
  {
    id: "u-emp1",
    email: "vikram@sharma-ca.example.com",
    full_name: "Vikram Joshi",
    phone: null,
    role_name: "EMPLOYEE",
    is_active: true,
    is_verified: true,
    last_login_at: "2026-03-01T09:15:00Z",
    created_at: "2026-01-05T00:00:00Z",
  },
];

function pageOf<T>(items: T[]): Page<T> {
  return {
    items,
    total: items.length,
    page: 1,
    page_size: 50,
  };
}

export function handleDemoRequest<T>(path: string, method = "GET"): T | null {
  const cleanPath = path.split("?")[0];

  // Auth & Org
  if (cleanPath === "/auth/me") return DEMO_ADMIN as unknown as T;
  if (cleanPath === "/org/current" || cleanPath === "/org") return DEMO_ORG as unknown as T;
  if (cleanPath === "/users") return DEMO_USERS as unknown as T;

  // Clients
  if (cleanPath === "/clients") return pageOf(DEMO_CLIENTS) as unknown as T;
  if (cleanPath.startsWith("/clients/c1/summary")) {
    return {
      client: DEMO_CLIENTS[0],
      counts: { documents: 2, tasks: 1, invoices: 1, requests: 1 },
      outstanding_amount: "5310.00",
      whatsapp_status: "OPTED_IN",
      last_message_at: "2026-03-01T14:10:00Z",
      pending_requests: [
        {
          id: "req1",
          title: "Bank Statements & Form 16 for ITR",
          status: "ACTIVE",
          due_date: "2026-04-15",
          pending_items: ["Bank Statement FY 2025-26", "Zerodha Annual P&L Statement"],
        },
      ],
      open_tasks: [
        { id: "t1", title: "ITR Filing FY 2024-25", status: "UNDER_REVIEW", service_type: "ITR", due_date: "2026-03-31" },
      ],
    } as unknown as T;
  }
  if (cleanPath.startsWith("/clients/")) {
    const id = cleanPath.split("/")[2];
    const found = DEMO_CLIENTS.find((c) => c.id === id) ?? DEMO_CLIENTS[0];
    return found as unknown as T;
  }

  // Documents
  if (cleanPath === "/documents") return pageOf(DEMO_DOCUMENTS) as unknown as T;
  if (cleanPath.startsWith("/documents/d1")) return DEMO_DOCUMENT_DETAIL as unknown as T;
  if (cleanPath.startsWith("/documents/")) return { ...DEMO_DOCUMENTS[0], ...DEMO_DOCUMENT_DETAIL } as unknown as T;

  // Requests
  if (cleanPath === "/document-requests") return pageOf(DEMO_REQUESTS) as unknown as T;

  // Tasks
  if (cleanPath === "/tasks") return pageOf(DEMO_TASKS) as unknown as T;

  // Invoices & Payments
  if (cleanPath === "/invoices") return pageOf(DEMO_INVOICES) as unknown as T;
  if (cleanPath.startsWith("/invoices/")) return DEMO_INVOICES[0] as unknown as T;
  if (cleanPath === "/payments") return pageOf(DEMO_PAYMENTS) as unknown as T;

  // WhatsApp
  if (cleanPath === "/whatsapp/account") {
    return {
      provider: "mock",
      display_phone_number: "+91 98000 00001",
      phone_number_id: "mock-phone-id",
      business_account_id: "mock-waba",
      status: "ACTIVE",
      webhook_url: "https://prodesk-ca.vercel.app/api/v1/whatsapp/webhook",
      verify_token_configured: true,
      last_verified_at: "2026-03-01T12:00:00Z",
      access_token_set: true,
      access_token_hint: "EAAG...3a2f",
      app_secret_set: true,
    } as unknown as T;
  }
  if (cleanPath === "/whatsapp/templates") {
    return [
      {
        id: "tpl1",
        key: "DOCUMENT_READY",
        name: "document_delivered_v2",
        language: "en",
        category: "UTILITY",
        status: "APPROVED",
        body_preview: "Namaste {{1}}, your {{2}} is ready from {{3}}. Download here: {{4}}",
        variables: ["client_name", "document_type", "firm_name", "link"],
        has_url_button: true,
        last_error: null,
      },
      {
        id: "tpl2",
        key: "PAYMENT_REMINDER",
        name: "invoice_payment_reminder",
        language: "en",
        category: "UTILITY",
        status: "APPROVED",
        body_preview: "Dear {{1}}, invoice {{2}} for {{3}} is due on {{4}}. Settle online: {{5}}",
        variables: ["client_name", "invoice_number", "amount", "due_date", "link"],
        has_url_button: true,
        last_error: null,
      },
    ] as unknown as T;
  }
  if (cleanPath === "/conversations") return pageOf(DEMO_CONVERSATIONS) as unknown as T;
  if (cleanPath === "/conversations/conv1") return DEMO_CONVERSATIONS[0] as unknown as T;
  if (cleanPath.includes("/messages")) return pageOf(DEMO_MESSAGES) as unknown as T;

  // Compliance
  if (cleanPath === "/compliance/events") return DEMO_COMPLIANCE as unknown as T;

  // Insights & Dashboard
  if (cleanPath === "/insights/dashboard") {
    return {
      active_clients: 24,
      documents_under_review: 3,
      tasks_due_soon: 5,
      tasks_overdue: 1,
      outstanding_invoices_total: "42500.00",
      unread_conversations: 2,
    } as unknown as T;
  }
  if (cleanPath.startsWith("/insights/reports/")) {
    return {
      columns: ["month", "new_clients", "total_clients"],
      rows: [
        { month: "Jan 2026", new_clients: 8, total_clients: 18 },
        { month: "Feb 2026", new_clients: 6, total_clients: 24 },
      ],
    } as unknown as T;
  }
  if (cleanPath === "/insights/support") {
    return {
      items: [
        {
          id: "sup1",
          client_id: "c1",
          client: { id: "c1", name: "Rahul Mehta" },
          request_type: "CALLBACK",
          message: "Please call regarding capital gains computation for ancestral property sale.",
          status: "OPEN",
          created_at: "2026-03-01T12:00:00Z",
        },
      ],
      total: 1,
      page: 1,
      page_size: 50,
    } as unknown as T;
  }
  if (cleanPath === "/insights/ask") {
    return {
      answer: "There are currently 2 clients with pending document submissions: Rahul Mehta (Bank Statements) and Mehta Textiles LLP (Feb Invoices).",
      columns: ["client", "pending_items", "due_date"],
      rows: [
        { client: "Rahul Mehta", pending_items: "Bank Statement FY2526, Zerodha P&L", due_date: "15 Apr 2026" },
        { client: "Mehta Textiles LLP", pending_items: "GSTR-2B discrepancy reconciliation", due_date: "10 Mar 2026" },
      ],
      disclaimer: "Generated from verified practice database records.",
    } as unknown as T;
  }

  // Client Portal
  if (cleanPath === "/portal/auth/me") {
    return {
      id: "c1",
      name: "Rahul Mehta",
      phone: "+91 98765 43210",
      email: "rahul.mehta@example.com",
      client_type: "INDIVIDUAL",
      pan: "ABCPM1234K",
      gstin: "—",
      address: "B-12 Woodland Park, Aundh, Pune 411007",
      whatsapp_opt_in: true,
      organization: {
        name: "Sharma & Associates Chartered Accountants",
        phone: "+91 98000 00001",
        email: "office@sharma-ca.example.com",
        address: "Suite 402, Trade Tower, Pune 411016",
      },
    } as unknown as T;
  }
  if (cleanPath === "/portal/dashboard") {
    return {
      client_name: "Rahul Mehta",
      firm_name: "Sharma & Associates",
      documents: 2,
      pending_requests: 1,
      open_invoices: 1,
      outstanding: "5310.00",
      requests: [
        {
          id: "req1",
          title: "Bank Statements & Form 16 for ITR",
          due_date: "2026-04-15",
          items: [
            { id: "i1", name: "Form 16 (Part A & B)", status: "RECEIVED" },
            { id: "i2", name: "Bank Statement FY 2025-26", status: "PENDING" },
          ],
        },
      ],
      tasks: [
        {
          title: "ITR Filing FY 2024-25 (AY 2025-26)",
          status: "UNDER_REVIEW",
          service_type: "ITR",
        },
      ],
    } as unknown as T;
  }
  if (cleanPath === "/portal/documents") return pageOf(DEMO_DOCUMENTS) as unknown as T;
  if (cleanPath === "/portal/requests") return pageOf(DEMO_REQUESTS) as unknown as T;
  if (cleanPath === "/portal/tasks") {
    return [
      {
        id: "t1",
        title: "ITR Filing FY 2024-25 (AY 2025-26)",
        service_type: "ITR",
        financial_year: "2024-25",
        status: "UNDER_REVIEW",
        status_label: "Under Review by Partner",
        filed_at: null,
      },
    ] as unknown as T;
  }
  if (cleanPath === "/portal/invoices") return pageOf(DEMO_INVOICES) as unknown as T;
  if (cleanPath === "/portal/payments") return pageOf(DEMO_PAYMENTS) as unknown as T;
  if (cleanPath === "/portal/messages") {
    return [
      {
        direction: "OUTBOUND",
        body: "Namaste Rahul ji, your ITR Acknowledgement has been uploaded and approved.",
        timestamp: "2026-03-01T14:05:00Z",
      },
      {
        direction: "INBOUND",
        body: "Sir, does the ITR refund get credited directly to my HDFC account?",
        timestamp: "2026-03-01T14:10:00Z",
      },
    ] as unknown as T;
  }
  if (cleanPath === "/portal/support") {
    return {
      items: [
        {
          id: "sup1",
          request_type: "CALLBACK",
          message: "Please call regarding capital gains computation.",
          status: "OPEN",
        },
      ],
    } as unknown as T;
  }

  // Generic mutation fallback
  if (method === "POST" || method === "PUT" || method === "PATCH") {
    return { success: true, message: "Demo action completed successfully" } as unknown as T;
  }

  return null;
}

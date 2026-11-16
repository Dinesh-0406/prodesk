export const cn = (...classes: (string | false | null | undefined)[]) => classes.filter(Boolean).join(" ");

const inr = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 });

export const money = (v: string | number | null | undefined) => inr.format(Number(v ?? 0));

export function fmtDate(v: string | null | undefined): string {
  if (!v) return "—";
  const d = new Date(v.length === 10 ? `${v}T00:00:00` : v);
  return d.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

export function fmtDateTime(v: string | null | undefined): string {
  if (!v) return "—";
  return new Date(v).toLocaleString("en-IN", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}

export function timeAgo(v: string | null | undefined): string {
  if (!v) return "";
  const s = Math.round((Date.now() - new Date(v).getTime()) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

const ACRONYMS = new Set(["ITR", "GST", "TDS", "PAN", "OTP", "ROC", "LLP", "UPI", "SAC", "FY", "AI", "CA"]);

export const humanize = (v: string | null | undefined) =>
  (v ?? "")
    .split("_")
    .filter(Boolean)
    .map((w) => (ACRONYMS.has(w.toUpperCase()) ? w.toUpperCase() : w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()))
    .join(" ");

export function fileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export const isOverdue = (due: string | null | undefined) => !!due && new Date(`${due}T23:59:59`) < new Date();

export const DOCUMENT_TYPES = [
  "ITR_ACKNOWLEDGEMENT", "ITR_COMPUTATION", "BALANCE_SHEET", "PROFIT_LOSS", "GST_RETURN", "GST_CERTIFICATE",
  "TDS_DOCUMENT", "AUDIT_REPORT", "INVOICE", "RECEIPT", "PAN", "AADHAAR", "BANK_STATEMENT", "OTHER",
] as const;
export const CLIENT_TYPES = ["INDIVIDUAL", "PROPRIETORSHIP", "PARTNERSHIP", "LLP", "COMPANY", "TRUST", "OTHER"] as const;
export const TASK_STATUSES = [
  "NEW_REQUEST", "DOCUMENTS_PENDING", "DOCUMENTS_RECEIVED", "WORK_IN_PROGRESS", "UNDER_REVIEW", "FILED", "COMPLETED", "DELIVERED",
] as const;
export const SERVICE_TYPES = ["ITR", "GST", "TDS", "AUDIT", "ROC", "ACCOUNTING", "ADVISORY", "OTHER"] as const;
export const PRIORITIES = ["LOW", "MEDIUM", "HIGH", "URGENT"] as const;

export function financialYears(count = 6): string[] {
  const now = new Date();
  const start = now.getMonth() >= 3 ? now.getFullYear() : now.getFullYear() - 1;
  return Array.from({ length: count }, (_, i) => {
    const s = start - i;
    return `${s}-${String(s + 1).slice(-2)}`;
  });
}

export function downloadBlob(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

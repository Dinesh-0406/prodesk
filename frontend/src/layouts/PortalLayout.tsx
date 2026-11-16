import {
  CreditCard,
  FileCheck,
  FileSpreadsheet,
  FileText,
  Headphones,
  LayoutDashboard,
  LogOut,
  MessageSquare,
  ShieldCheck,
  UserCheck,
} from "lucide-react";
import type { ReactNode } from "react";
import { NavLink, Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { usePortal } from "../hooks/usePortal";
import { cn } from "../utils/format";

const LINKS = [
  { to: "/portal", label: "Dashboard", icon: LayoutDashboard },
  { to: "/portal/documents", label: "My Documents", icon: FileText },
  { to: "/portal/requests", label: "Document Requests", icon: FileCheck },
  { to: "/portal/tasks", label: "Tasks", icon: FileSpreadsheet },
  { to: "/portal/invoices", label: "Invoices", icon: CreditCard },
  { to: "/portal/payments", label: "Payments", icon: ShieldCheck },
  { to: "/portal/messages", label: "WhatsApp", icon: MessageSquare },
  { to: "/portal/support", label: "Support", icon: Headphones },
  { to: "/portal/profile", label: "My Profile", icon: UserCheck },
] as const;

export function PortalLayout() {
  const { authenticated, clientName, firmName, logout } = usePortal();
  const { loginDemo: loginAdmin } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();

  if (!authenticated) {
    return <Navigate to={`/portal/login?next=${encodeURIComponent(loc.pathname)}`} replace />;
  }

  return (
    <div className="min-h-screen bg-ink-50/50 flex flex-col font-sans">
      {/* Client Portal Header */}
      <header className="sticky top-0 z-30 border-b border-ink-200/80 bg-white/95 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 sm:px-6">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-brand-600 to-brand-800 text-white shadow-xs">
              <span className="font-bold text-sm">{(firmName || "P").slice(0, 1).toUpperCase()}</span>
            </div>
            <div className="leading-tight">
              <div className="flex items-center gap-2">
                <p className="text-sm font-semibold text-ink-950">{firmName}</p>
                <span className="hidden sm:inline-flex items-center rounded-md bg-emerald-50 px-1.5 py-0.5 text-[10px] font-medium text-emerald-700">
                  Client Portal
                </span>
              </div>
              <p className="text-xs text-ink-500">Welcome, {clientName}</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Demo Switcher */}
            <div className="hidden md:flex items-center gap-1.5 rounded-full border border-brand-200/80 bg-brand-50/70 px-2.5 py-1 text-xs">
              <span className="flex h-2 w-2 rounded-full bg-brand-500 animate-pulse" />
              <span className="font-semibold text-brand-950">Demo Client</span>
              <span className="text-brand-300">·</span>
              <button
                type="button"
                onClick={() => {
                  loginAdmin("FIRM_ADMIN");
                  nav("/");
                }}
                className="font-medium text-brand-800 hover:text-brand-950 hover:underline"
              >
                Switch to CA Workspace →
              </button>
            </div>

            <div className="hidden sm:flex items-center gap-2 rounded-full border border-ink-200/80 bg-ink-50 px-3 py-1 text-xs text-ink-600">
              <ShieldCheck className="h-3.5 w-3.5 text-emerald-600" />
              <span>Verified Session</span>
            </div>
            <button
              onClick={logout}
              className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium text-ink-600 hover:bg-ink-100 hover:text-ink-900 transition-colors"
            >
              <LogOut className="h-3.5 w-3.5" />
              <span>Sign out</span>
            </button>
          </div>
        </div>

        {/* Horizontal Navigation Pills */}
        <nav
          className="mx-auto flex max-w-6xl gap-1 overflow-x-auto px-4 sm:px-6 no-scrollbar"
          aria-label="Portal"
        >
          {LINKS.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/portal"}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-2 whitespace-nowrap border-b-2 px-3.5 py-2.5 text-xs font-medium transition-all",
                  isActive
                    ? "border-brand-600 text-brand-800 font-semibold"
                    : "border-transparent text-ink-600 hover:border-ink-300 hover:text-ink-950"
                )
              }
            >
              <Icon className="h-3.5 w-3.5" />
              {label}
            </NavLink>
          ))}
        </nav>
      </header>

      {/* Main Content Viewport */}
      <main className="mx-auto w-full max-w-6xl flex-1 p-4 sm:p-6 lg:p-8 animate-fadeIn">
        <Outlet />
      </main>

      {/* Footer */}
      <footer className="border-t border-ink-200/60 bg-white py-4 text-center text-xs text-ink-400">
        <div className="mx-auto max-w-6xl px-4 flex flex-wrap items-center justify-between gap-2">
          <span>Secured by ProDesk Client Communication Platform</span>
          <span className="flex items-center gap-1">
            <ShieldCheck className="h-3.5 w-3.5 text-brand-600" />
            256-bit TLS encrypted
          </span>
        </div>
      </footer>
    </div>
  );
}

export function AuthShell({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
}) {
  return (
    <div className="relative flex min-h-screen items-center justify-center bg-ink-50/60 p-4 sm:p-6">
      {/* Background Subtle Gradient & Grid */}
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(#e5e7eb_1px,transparent_1px)] [background-size:20px_20px] opacity-60" />

      <div className="relative w-full max-w-md animate-fadeIn">
        {/* Brand Mark */}
        <div className="mb-6 flex flex-col items-center justify-center text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-tr from-brand-700 via-brand-600 to-teal-500 shadow-md shadow-brand-900/10">
            <span className="text-xl font-bold tracking-tight text-white font-mono">P</span>
          </div>
          <span className="mt-3 text-lg font-bold tracking-tight text-ink-950">ProDesk</span>
          <span className="text-xs text-ink-400">Professional CA Workspace</span>
        </div>

        {/* Card */}
        <div className="rounded-2xl border border-ink-200/90 bg-white p-6 sm:p-8 shadow-card">
          <div className="mb-5 text-center">
            <h1 className="text-lg font-semibold tracking-tight text-ink-950">{title}</h1>
            {subtitle && <p className="mt-1 text-xs text-ink-500 leading-relaxed">{subtitle}</p>}
          </div>
          {children}
        </div>

        {/* Security Trust Footnote */}
        <div className="mt-6 flex items-center justify-center gap-2 text-[11px] text-ink-400">
          <ShieldCheck className="h-3.5 w-3.5 text-emerald-600" />
          <span>Encrypted with bank-grade security protocols</span>
        </div>
      </div>
    </div>
  );
}

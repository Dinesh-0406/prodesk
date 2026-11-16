import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  BarChart3,
  Bell,
  Bot,
  CalendarClock,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  FilePlus2,
  FileText,
  FolderInput,
  LayoutDashboard,
  LifeBuoy,
  ListChecks,
  ListPlus,
  LogOut,
  Menu,
  MessageCircle,
  Plus,
  Receipt,
  ReceiptIndianRupee,
  Search,
  Settings,
  Sparkles,
  UserPlus,
  Users,
  UserSquare2,
  X,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { CommandPalette } from "../components/CommandPalette";
import { Avatar, Badge, Button } from "../components/ui";
import { ClientFormModal } from "../features/clients/ClientForm";
import { UploadDocumentModal } from "../features/documents/UploadDocumentModal";
import { InvoiceFormModal } from "../features/invoices/InvoiceFormModal";
import { RequestFormModal } from "../features/requests/RequestFormModal";
import { TaskFormModal } from "../features/tasks/TaskFormModal";
import { useAuth } from "../hooks/useAuth";
import { usePortal } from "../hooks/usePortal";
import { insightApi } from "../services/endpoints";
import { cn, timeAgo } from "../utils/format";

export interface NavEntry {
  to: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  perm: string;
  end?: boolean;
  section?: "WORKSPACE" | "OPERATIONS" | "INSIGHTS" | "ADMIN";
}

export const NAV: NavEntry[] = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, perm: "CLIENT_VIEW", end: true, section: "WORKSPACE" },
  { to: "/clients", label: "Clients", icon: Users, perm: "CLIENT_VIEW", section: "WORKSPACE" },
  { to: "/documents", label: "Documents", icon: FileText, perm: "DOCUMENT_VIEW", section: "WORKSPACE" },
  { to: "/tasks", label: "Tasks", icon: ListChecks, perm: "TASK_VIEW", section: "WORKSPACE" },
  { to: "/document-requests", label: "Document Requests", icon: FolderInput, perm: "TASK_VIEW", section: "OPERATIONS" },
  { to: "/whatsapp", label: "WhatsApp", icon: MessageCircle, perm: "WHATSAPP_VIEW", section: "OPERATIONS" },
  { to: "/compliance", label: "Compliance Calendar", icon: CalendarClock, perm: "TASK_VIEW", section: "OPERATIONS" },
  { to: "/invoices", label: "Invoices & Payments", icon: Receipt, perm: "INVOICE_VIEW", section: "OPERATIONS" },
  { to: "/reports", label: "Reports", icon: BarChart3, perm: "REPORT_VIEW", section: "INSIGHTS" },
  { to: "/assistant", label: "AI Assistant", icon: Bot, perm: "CLIENT_VIEW", section: "INSIGHTS" },
  { to: "/support", label: "Client Requests", icon: LifeBuoy, perm: "CLIENT_VIEW", section: "INSIGHTS" },
  { to: "/employees", label: "Employees", icon: UserSquare2, perm: "USER_MANAGE", section: "ADMIN" },
  { to: "/settings", label: "Settings", icon: Settings, perm: "SETTINGS_MANAGE", section: "ADMIN" },
];

const SECTIONS = ["WORKSPACE", "OPERATIONS", "INSIGHTS", "ADMIN"] as const;

function NotificationDrawer({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const nav = useNavigate();
  const { data = [] } = useQuery({
    queryKey: ["notifications"],
    queryFn: insightApi.notifications,
    refetchInterval: 30000,
  });

  const unread = data.filter((n) => !n.read_at).length;

  const markAllRead = async () => {
    await insightApi.markRead();
    qc.invalidateQueries({ queryKey: ["notifications"] });
  };

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 overflow-hidden bg-ink-950/25 backdrop-blur-xs animate-fade-in"
      onMouseDown={onClose}
    >
      <div className="absolute inset-y-0 right-0 flex max-w-full pl-10">
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Notifications"
          onMouseDown={(e) => e.stopPropagation()}
          className="w-screen max-w-sm bg-white shadow-modal flex flex-col border-l border-ink-200 animate-slide-left"
        >
          {/* Header */}
          <div className="flex items-center justify-between border-b border-ink-100 px-5 py-4">
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-semibold text-ink-950">Notifications</h3>
              {unread > 0 && (
                <span className="rounded-full bg-brand-50 border border-brand-200 px-2 py-0.5 text-[11px] font-bold text-brand-700">
                  {unread} new
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              {unread > 0 && (
                <button
                  type="button"
                  onClick={markAllRead}
                  className="text-xs font-medium text-brand-700 hover:text-brand-800 transition-colors"
                >
                  Mark all read
                </button>
              )}
              <button
                onClick={onClose}
                aria-label="Close notifications"
                className="rounded-lg p-1 text-ink-400 hover:bg-ink-100 hover:text-ink-700 transition-colors"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>

          {/* List */}
          <div className="flex-1 overflow-y-auto divide-y divide-ink-100/80">
            {data.length === 0 ? (
              <div className="flex flex-col items-center justify-center gap-2 px-6 py-16 text-center text-xs text-ink-500">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600 mb-1">
                  <Check className="h-5 w-5" />
                </div>
                <p className="font-semibold text-ink-900 text-sm">All caught up</p>
                <p>No new notifications at this time.</p>
              </div>
            ) : (
              data.map((n) => (
                <button
                  key={n.id}
                  type="button"
                  onClick={() => {
                    onClose();
                    if (n.link) nav(n.link);
                  }}
                  className={cn(
                    "flex w-full items-start gap-3 p-4 text-left transition-colors duration-100 hover:bg-ink-50/80",
                    !n.read_at && "bg-brand-50/40"
                  )}
                >
                  <div
                    className={cn(
                      "mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border",
                      !n.read_at
                        ? "bg-brand-100 text-brand-700 border-brand-200"
                        : "bg-ink-100 text-ink-500 border-ink-200"
                    )}
                  >
                    <Bell className="h-3.5 w-3.5" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className={cn("text-xs leading-snug", !n.read_at ? "font-semibold text-ink-950" : "font-medium text-ink-800")}>
                      {n.title}
                    </p>
                    {n.body && (
                      <p className="mt-1 line-clamp-2 text-xs text-ink-500 leading-relaxed font-normal">{n.body}</p>
                    )}
                    <span className="mt-1.5 block text-[10px] text-ink-400 font-medium">
                      {timeAgo(n.created_at)}
                    </span>
                  </div>
                </button>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export function AppLayout() {
  const { me, can, logout } = useAuth();
  const { loginDemo: loginClient } = usePortal();
  const nav = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem("prodesk.sidebar.collapsed") === "true";
    } catch {
      return false;
    }
  });

  const [cmdOpen, setCmdOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [quickCreateOpen, setQuickCreateOpen] = useState(false);

  // Active Modals
  const [activeModal, setActiveModal] = useState<
    "" | "new-client" | "upload-doc" | "new-task" | "new-invoice" | "request-doc"
  >("");

  const profileMenuRef = useRef<HTMLDivElement>(null);
  const quickCreateRef = useRef<HTMLDivElement>(null);

  // Notification count
  const { data: notifications = [] } = useQuery({
    queryKey: ["notifications"],
    queryFn: insightApi.notifications,
    refetchInterval: 30000,
  });
  const unreadNotifs = notifications.filter((n) => !n.read_at).length;

  // Toggle collapsed
  const toggleCollapse = () => {
    const next = !collapsed;
    setCollapsed(next);
    try {
      localStorage.setItem("prodesk.sidebar.collapsed", String(next));
    } catch {
      // ignore
    }
  };

  // Keyboard shortcut for Command Palette
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setCmdOpen((prev) => !prev);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  // Close dropdowns on outside click
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (profileMenuRef.current && !profileMenuRef.current.contains(e.target as Node)) {
        setProfileOpen(false);
      }
      if (quickCreateRef.current && !quickCreateRef.current.contains(e.target as Node)) {
        setQuickCreateOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const accessibleNav = NAV.filter((n) => can(n.perm));

  return (
    <div className="flex min-h-screen bg-[#f8faf9]">
      {/* ----------------------------- SIDEBAR ----------------------------- */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex flex-col border-r border-ink-200/80 bg-white transition-all duration-200 ease-in-out lg:static shrink-0 select-none",
          collapsed ? "w-[68px]" : "w-60",
          mobileOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
        )}
      >
        {/* Brand Area */}
        <div
          className={cn(
            "flex h-14 items-center border-b border-ink-100/90 px-3.5",
            collapsed ? "justify-center" : "justify-between"
          )}
        >
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="relative flex h-8 w-8 items-center justify-center rounded-xl bg-brand-800 text-white shadow-xs shrink-0 ring-1 ring-brand-900/10">
              <span className="font-bold text-sm tracking-tight">P</span>
              <span className="absolute -bottom-0.5 -right-0.5 h-2 w-2 rounded-full bg-emerald-400 ring-2 ring-white" />
            </div>
            {!collapsed && (
              <div className="min-w-0 truncate leading-tight">
                <span className="font-bold text-sm text-ink-950 tracking-tight block">ProDesk</span>
                <span className="text-[11px] font-medium text-ink-500 truncate block">
                  {me?.organization_name || "Practice Workspace"}
                </span>
              </div>
            )}
          </div>
          <button
            type="button"
            onClick={() => setMobileOpen(false)}
            aria-label="Close sidebar"
            className="rounded-lg p-1 text-ink-400 hover:bg-ink-100 hover:text-ink-700 lg:hidden"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Primary Navigation grouped by section */}
        <nav
          className="flex-1 overflow-y-auto px-2.5 py-3 space-y-4"
          aria-label="Main"
        >
          {SECTIONS.map((sec) => {
            const sectionItems = accessibleNav.filter((n) => n.section === sec);
            if (sectionItems.length === 0) return null;

            return (
              <div key={sec} className="space-y-0.5">
                {!collapsed && (
                  <div className="px-2.5 pb-1 pt-1 text-[10px] font-bold uppercase tracking-wider text-ink-400">
                    {sec}
                  </div>
                )}
                {sectionItems.map(({ to, label, icon: Icon, end }) => (
                  <NavLink
                    key={to}
                    to={to}
                    end={end}
                    title={collapsed ? label : undefined}
                    onClick={() => setMobileOpen(false)}
                    className={({ isActive }) =>
                      cn(
                        "group relative flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-xs font-medium transition-all duration-150 select-none",
                        isActive
                          ? "bg-brand-50/90 text-brand-900 font-semibold shadow-2xs"
                          : "text-ink-600 hover:bg-ink-100/70 hover:text-ink-950",
                        collapsed && "justify-center px-0"
                      )
                    }
                  >
                    {({ isActive }) => (
                      <>
                        <Icon
                          className={cn(
                            "h-4 w-4 shrink-0 transition-colors",
                            isActive ? "text-brand-700" : "text-ink-500 group-hover:text-ink-800"
                          )}
                        />
                        {!collapsed ? (
                          <span className="truncate">{label}</span>
                        ) : (
                          <span className="sr-only">{label}</span>
                        )}
                        {isActive && !collapsed && (
                          <span className="ml-auto h-1.5 w-1.5 rounded-full bg-brand-600" />
                        )}
                      </>
                    )}
                  </NavLink>
                ))}
              </div>
            );
          })}
        </nav>

        {/* Collapse toggle footer */}
        <div className="hidden lg:flex items-center justify-between border-t border-ink-100/90 p-2.5">
          <button
            type="button"
            onClick={toggleCollapse}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className={cn(
              "flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-xs font-medium text-ink-500 hover:bg-ink-100/70 hover:text-ink-800 transition-colors",
              collapsed && "justify-center"
            )}
          >
            {collapsed ? (
              <ChevronRight className="h-4 w-4" />
            ) : (
              <>
                <ChevronLeft className="h-4 w-4" />
                <span>Collapse</span>
              </>
            )}
          </button>
        </div>
      </aside>

      {/* Mobile Backdrop */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-30 bg-ink-950/30 backdrop-blur-xs lg:hidden animate-fade-in"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* ----------------------------- MAIN WRAPPER ----------------------------- */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* TOP BAR */}
        <header className="sticky top-0 z-20 flex h-14 items-center justify-between gap-3 border-b border-ink-200/80 bg-white/95 px-4 backdrop-blur-md">
          {/* Left: Mobile hamburger & Command Palette trigger button */}
          <div className="flex items-center gap-2.5 flex-1 max-w-lg">
            <button
              type="button"
              className="rounded-lg p-1.5 text-ink-500 hover:bg-ink-100 hover:text-ink-800 transition-colors lg:hidden"
              aria-label="Open menu"
              onClick={() => setMobileOpen(true)}
            >
              <Menu className="h-5 w-5" />
            </button>

            {/* Global Search trigger styled as Command Center */}
            <button
              type="button"
              onClick={() => setCmdOpen(true)}
              aria-label="Global search"
              className="flex w-full items-center justify-between rounded-lg border border-ink-200 bg-ink-50/70 px-3 py-1.5 text-xs text-ink-400 hover:border-ink-300 hover:bg-white hover:text-ink-600 transition-all duration-150 shadow-2xs group"
            >
              <div className="flex items-center gap-2 min-w-0 truncate">
                <Search className="h-3.5 w-3.5 text-ink-400 group-hover:text-brand-600 transition-colors shrink-0" />
                <span className="truncate">Search clients, documents, tasks...</span>
              </div>
              <kbd className="hidden sm:inline-flex items-center gap-0.5 rounded border border-ink-200 bg-white px-1.5 py-0.5 text-[10px] font-medium text-ink-500 shadow-2xs">
                ⌘K
              </kbd>
            </button>
          </div>

          {/* Right: Demo Switcher, Quick Create, Notifications, Profile */}
          <div className="flex items-center gap-2">
            {/* Demo Mode Switcher */}
            <div className="hidden xl:flex items-center gap-1.5 rounded-full border border-emerald-200/80 bg-emerald-50/70 px-2.5 py-1 text-xs">
              <span className="flex h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
              <span className="font-semibold text-emerald-950">Demo Mode</span>
              <span className="text-emerald-300">·</span>
              <button
                type="button"
                onClick={() => {
                  loginClient();
                  nav("/portal");
                }}
                className="font-medium text-emerald-800 hover:text-emerald-950 hover:underline"
              >
                Switch to Client Portal →
              </button>
            </div>

            {/* Quick Create Dropdown */}
            <div className="relative" ref={quickCreateRef}>
              <Button
                size="sm"
                variant="primary"
                onClick={() => setQuickCreateOpen(!quickCreateOpen)}
                className="gap-1.5 text-xs shadow-xs"
              >
                <Plus className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">New</span>
                <ChevronDown className="h-3 w-3 opacity-80" />
              </Button>

              {quickCreateOpen && (
                <div className="absolute right-0 mt-1.5 w-52 rounded-xl border border-ink-200 bg-white py-1 shadow-popover z-30 animate-slide-down">
                  <div className="px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider text-ink-400 border-b border-ink-100">
                    Quick Create
                  </div>
                  {can("CLIENT_CREATE") && (
                    <button
                      type="button"
                      onClick={() => {
                        setQuickCreateOpen(false);
                        setActiveModal("new-client");
                      }}
                      className="flex w-full items-center gap-2.5 px-3 py-2 text-left text-xs text-ink-700 hover:bg-ink-50 hover:text-ink-950 transition-colors"
                    >
                      <UserPlus className="h-4 w-4 text-brand-700" />
                      <span>Add new client</span>
                    </button>
                  )}
                  {can("DOCUMENT_UPLOAD") && (
                    <button
                      type="button"
                      onClick={() => {
                        setQuickCreateOpen(false);
                        setActiveModal("upload-doc");
                      }}
                      className="flex w-full items-center gap-2.5 px-3 py-2 text-left text-xs text-ink-700 hover:bg-ink-50 hover:text-ink-950 transition-colors"
                    >
                      <FilePlus2 className="h-4 w-4 text-sky-600" />
                      <span>Upload document</span>
                    </button>
                  )}
                  {can("TASK_CREATE") && (
                    <button
                      type="button"
                      onClick={() => {
                        setQuickCreateOpen(false);
                        setActiveModal("new-task");
                      }}
                      className="flex w-full items-center gap-2.5 px-3 py-2 text-left text-xs text-ink-700 hover:bg-ink-50 hover:text-ink-950 transition-colors"
                    >
                      <ListPlus className="h-4 w-4 text-emerald-600" />
                      <span>Create task</span>
                    </button>
                  )}
                  {can("INVOICE_CREATE") && (
                    <button
                      type="button"
                      onClick={() => {
                        setQuickCreateOpen(false);
                        setActiveModal("new-invoice");
                      }}
                      className="flex w-full items-center gap-2.5 px-3 py-2 text-left text-xs text-ink-700 hover:bg-ink-50 hover:text-ink-950 transition-colors"
                    >
                      <ReceiptIndianRupee className="h-4 w-4 text-amber-600" />
                      <span>Create invoice</span>
                    </button>
                  )}
                  {can("DOCUMENT_REQUEST_CREATE") && (
                    <button
                      type="button"
                      onClick={() => {
                        setQuickCreateOpen(false);
                        setActiveModal("request-doc");
                      }}
                      className="flex w-full items-center gap-2.5 px-3 py-2 text-left text-xs text-ink-700 hover:bg-ink-50 hover:text-ink-950 transition-colors"
                    >
                      <FolderInput className="h-4 w-4 text-violet-600" />
                      <span>Request documents</span>
                    </button>
                  )}
                </div>
              )}
            </div>

            {/* Notifications trigger */}
            <button
              type="button"
              aria-label="Notifications"
              onClick={() => setNotifOpen(true)}
              className="relative rounded-lg p-2 text-ink-500 hover:bg-ink-100 hover:text-ink-800 transition-colors"
            >
              <Bell className="h-4 w-4" />
              {unreadNotifs > 0 && (
                <span className="absolute top-1 right-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-rose-600 px-1 text-[10px] font-bold text-white ring-2 ring-white">
                  {unreadNotifs}
                </span>
              )}
            </button>

            {/* User Profile Dropdown */}
            <div className="relative" ref={profileMenuRef}>
              <button
                type="button"
                aria-label="User profile"
                onClick={() => setProfileOpen(!profileOpen)}
                className="flex items-center gap-2 rounded-lg p-1 text-left hover:bg-ink-50 transition-colors"
              >
                <Avatar name={me?.full_name ?? "User"} size="sm" />
                <div className="hidden md:block min-w-0 text-left">
                  <p className="text-xs font-semibold text-ink-900 leading-tight truncate">
                    {me?.full_name}
                  </p>
                  <p className="text-[10px] text-ink-500 leading-tight truncate capitalize">
                    {me?.role.replace("_", " ").toLowerCase()}
                  </p>
                </div>
                <ChevronDown className="h-3 w-3 text-ink-400 hidden md:block" />
              </button>

              {profileOpen && (
                <div className="absolute right-0 mt-1.5 w-60 rounded-xl border border-ink-200 bg-white py-1.5 shadow-popover z-30 animate-slide-down">
                  <div className="px-3.5 py-2.5 border-b border-ink-100">
                    <p className="text-xs font-semibold text-ink-950">{me?.full_name}</p>
                    <p className="text-[11px] text-ink-500 truncate">{me?.email}</p>
                    <div className="mt-1.5 flex items-center gap-1.5">
                      <Badge value={me?.role ?? "EMPLOYEE"} />
                      {me?.is_verified && (
                        <span className="text-[10px] font-medium text-emerald-600 flex items-center gap-0.5">
                          <Check className="h-3 w-3" /> Verified
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="py-1">
                    <button
                      type="button"
                      onClick={() => {
                        setProfileOpen(false);
                        nav("/assistant");
                      }}
                      className="flex w-full items-center gap-2.5 px-3.5 py-2 text-left text-xs text-ink-700 hover:bg-ink-50 transition-colors"
                    >
                      <Sparkles className="h-3.5 w-3.5 text-brand-600" />
                      <span>AI Assistant</span>
                    </button>
                    {can("SETTINGS_MANAGE") && (
                      <button
                        type="button"
                        onClick={() => {
                          setProfileOpen(false);
                          nav("/settings");
                        }}
                        className="flex w-full items-center gap-2.5 px-3.5 py-2 text-left text-xs text-ink-700 hover:bg-ink-50 transition-colors"
                      >
                        <Settings className="h-3.5 w-3.5 text-ink-500" />
                        <span>Firm Settings</span>
                      </button>
                    )}
                  </div>

                  <div className="border-t border-ink-100 pt-1">
                    <button
                      type="button"
                      aria-label="Log out"
                      onClick={async () => {
                        setProfileOpen(false);
                        await logout();
                        nav("/login");
                      }}
                      className="flex w-full items-center gap-2.5 px-3.5 py-2 text-left text-xs text-rose-600 hover:bg-rose-50 transition-colors"
                    >
                      <LogOut className="h-3.5 w-3.5" />
                      <span>Sign out</span>
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </header>

        {/* Unverified Email Warning Bar */}
        {me && !me.is_verified && (
          <div className="flex items-center justify-between border-b border-amber-200/80 bg-amber-50 px-4 py-2 text-xs text-amber-900">
            <div className="flex items-center gap-2">
              <AlertCircle className="h-4 w-4 text-amber-600 shrink-0" />
              <span>
                Please verify your email address — check your inbox for the verification link.
              </span>
            </div>
          </div>
        )}

        {/* Content Outlet */}
        <main className="mx-auto w-full max-w-[1440px] flex-1 p-4 sm:p-6 lg:p-8">
          <Outlet />
        </main>
      </div>

      {/* ----------------------------- GLOBAL MODALS & DIALOGS ----------------------------- */}
      <CommandPalette
        open={cmdOpen}
        onClose={() => setCmdOpen(false)}
        onAction={(act) => setActiveModal(act)}
      />

      <NotificationDrawer open={notifOpen} onClose={() => setNotifOpen(false)} />

      {/* Quick Action Modals */}
      <ClientFormModal
        open={activeModal === "new-client"}
        onClose={() => setActiveModal("")}
        onSaved={(c) => nav(`/clients/${c.id}`)}
      />
      <UploadDocumentModal
        open={activeModal === "upload-doc"}
        onClose={() => setActiveModal("")}
        onUploaded={(d) => nav(`/documents/${d.id}`)}
      />
      <TaskFormModal
        open={activeModal === "new-task"}
        onClose={() => setActiveModal("")}
      />
      <InvoiceFormModal
        open={activeModal === "new-invoice"}
        onClose={() => setActiveModal("")}
      />
      <RequestFormModal
        open={activeModal === "request-doc"}
        onClose={() => setActiveModal("")}
      />
    </div>
  );
}

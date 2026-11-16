import { useQuery } from "@tanstack/react-query";
import {
  BarChart3,
  Bot,
  CalendarClock,
  FilePlus2,
  FileText,
  FolderInput,
  LayoutDashboard,
  LifeBuoy,
  ListChecks,
  ListPlus,
  MessageCircle,
  Receipt,
  ReceiptIndianRupee,
  Search,
  Settings,
  UserPlus,
  Users,
  UserSquare2,
  X,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { useDebounce } from "../hooks/useDebounce";
import { insightApi } from "../services/endpoints";
import { cn } from "../utils/format";

interface CommandItem {
  id: string;
  title: string;
  subtitle?: string;
  category: "Navigation" | "Actions" | "Clients" | "Documents" | "Tasks" | "Invoices" | "Conversations";
  icon: React.ComponentType<{ className?: string }>;
  onSelect: () => void;
  keywords?: string[];
  perm?: string;
}

export function CommandPalette({
  open,
  onClose,
  onAction,
}: {
  open: boolean;
  onClose: () => void;
  onAction?: (action: "new-client" | "upload-doc" | "new-task" | "new-invoice" | "request-doc") => void;
}) {
  const [q, setQ] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const nav = useNavigate();
  const { can } = useAuth();
  const dq = useDebounce(q, 200);

  // Search API results
  const { data: searchResults, isLoading } = useQuery({
    queryKey: ["search", dq],
    queryFn: () => insightApi.search(dq),
    enabled: dq.trim().length >= 2,
  });

  // Base navigation items
  const navItems: CommandItem[] = useMemo(
    () => [
      { id: "nav-dash", title: "Dashboard", category: "Navigation", icon: LayoutDashboard, onSelect: () => nav("/"), perm: "CLIENT_VIEW" },
      { id: "nav-clients", title: "Clients", category: "Navigation", icon: Users, onSelect: () => nav("/clients"), perm: "CLIENT_VIEW" },
      { id: "nav-docs", title: "Documents", category: "Navigation", icon: FileText, onSelect: () => nav("/documents"), perm: "DOCUMENT_VIEW" },
      { id: "nav-tasks", title: "Tasks", category: "Navigation", icon: ListChecks, onSelect: () => nav("/tasks"), perm: "TASK_VIEW" },
      { id: "nav-requests", title: "Document Requests", category: "Navigation", icon: FolderInput, onSelect: () => nav("/document-requests"), perm: "TASK_VIEW" },
      { id: "nav-wa", title: "WhatsApp Inbox", category: "Navigation", icon: MessageCircle, onSelect: () => nav("/whatsapp"), perm: "WHATSAPP_VIEW" },
      { id: "nav-compliance", title: "Compliance Calendar", category: "Navigation", icon: CalendarClock, onSelect: () => nav("/compliance"), perm: "TASK_VIEW" },
      { id: "nav-invoices", title: "Invoices & Payments", category: "Navigation", icon: Receipt, onSelect: () => nav("/invoices"), perm: "INVOICE_VIEW" },
      { id: "nav-reports", title: "Reports & Analytics", category: "Navigation", icon: BarChart3, onSelect: () => nav("/reports"), perm: "REPORT_VIEW" },
      { id: "nav-employees", title: "Employees", category: "Navigation", icon: UserSquare2, onSelect: () => nav("/employees"), perm: "USER_MANAGE" },
      { id: "nav-assistant", title: "AI Assistant", category: "Navigation", icon: Bot, onSelect: () => nav("/assistant"), perm: "CLIENT_VIEW" },
      { id: "nav-support", title: "Client Requests", category: "Navigation", icon: LifeBuoy, onSelect: () => nav("/support"), perm: "CLIENT_VIEW" },
      { id: "nav-settings", title: "Firm Settings", category: "Navigation", icon: Settings, onSelect: () => nav("/settings"), perm: "SETTINGS_MANAGE" },
    ],
    [nav]
  );

  // Quick action items
  const actionItems: CommandItem[] = useMemo(
    () => [
      {
        id: "act-new-client",
        title: "Add new client",
        subtitle: "Create client profile & record WhatsApp consent",
        category: "Actions",
        icon: UserPlus,
        perm: "CLIENT_CREATE",
        onSelect: () => onAction?.("new-client"),
      },
      {
        id: "act-upload-doc",
        title: "Upload document",
        subtitle: "Add file to client vault or internal draft",
        category: "Actions",
        icon: FilePlus2,
        perm: "DOCUMENT_UPLOAD",
        onSelect: () => onAction?.("upload-doc"),
      },
      {
        id: "act-new-task",
        title: "Create task",
        subtitle: "Assign filing, review or accounting task",
        category: "Actions",
        icon: ListPlus,
        perm: "TASK_CREATE",
        onSelect: () => onAction?.("new-task"),
      },
      {
        id: "act-new-invoice",
        title: "Create invoice",
        subtitle: "Draft professional GST invoice",
        category: "Actions",
        icon: ReceiptIndianRupee,
        perm: "INVOICE_CREATE",
        onSelect: () => onAction?.("new-invoice"),
      },
      {
        id: "act-request-docs",
        title: "Request documents from client",
        subtitle: "Send checklist via WhatsApp and client portal",
        category: "Actions",
        icon: FolderInput,
        perm: "DOCUMENT_REQUEST_CREATE",
        onSelect: () => onAction?.("request-doc"),
      },
    ],
    [onAction]
  );

  // Build filtered items list
  const filteredItems = useMemo(() => {
    const list: CommandItem[] = [];
    const query = q.trim().toLowerCase();

    // 1. If user typed a search query with >= 2 chars and API returned results
    if (searchResults && query.length >= 2) {
      if (searchResults.clients?.length) {
        searchResults.clients.forEach((c) => {
          list.push({
            id: `client-${c.id}`,
            title: c.title,
            subtitle: c.subtitle,
            category: "Clients",
            icon: Users,
            onSelect: () => nav(`/clients/${c.id}`),
          });
        });
      }
      if (searchResults.documents?.length) {
        searchResults.documents.forEach((d) => {
          list.push({
            id: `doc-${d.id}`,
            title: d.title,
            subtitle: d.subtitle,
            category: "Documents",
            icon: FileText,
            onSelect: () => nav(`/documents/${d.id}`),
          });
        });
      }
      if (searchResults.tasks?.length) {
        searchResults.tasks.forEach((t) => {
          list.push({
            id: `task-${t.id}`,
            title: t.title,
            subtitle: t.subtitle,
            category: "Tasks",
            icon: ListChecks,
            onSelect: () => nav(`/tasks?q=${encodeURIComponent(t.title)}`),
          });
        });
      }
      if (searchResults.invoices?.length) {
        searchResults.invoices.forEach((i) => {
          list.push({
            id: `inv-${i.id}`,
            title: i.title,
            subtitle: i.subtitle,
            category: "Invoices",
            icon: Receipt,
            onSelect: () => nav(`/invoices?open=${i.id}`),
          });
        });
      }
      if (searchResults.conversations?.length) {
        searchResults.conversations.forEach((cv) => {
          list.push({
            id: `conv-${cv.id}`,
            title: cv.title,
            subtitle: cv.subtitle,
            category: "Conversations",
            icon: MessageCircle,
            onSelect: () => nav(`/whatsapp?conversation=${cv.id}`),
          });
        });
      }
    }

    // 2. Filter actions and nav items based on text and user permissions
    const accessibleActions = actionItems.filter((i) => !i.perm || can(i.perm));
    const matchingActions = query
      ? accessibleActions.filter(
          (a) =>
            a.title.toLowerCase().includes(query) ||
            (a.subtitle && a.subtitle.toLowerCase().includes(query))
        )
      : accessibleActions;

    const accessibleNav = navItems.filter((i) => !i.perm || can(i.perm));
    const matchingNav = query
      ? accessibleNav.filter((n) => n.title.toLowerCase().includes(query))
      : accessibleNav;

    // Put actions first if empty or matching
    list.push(...matchingActions);
    list.push(...matchingNav);

    return list;
  }, [q, searchResults, actionItems, navItems, can, nav]);

  // Focus input on open
  useEffect(() => {
    if (open) {
      setQ("");
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  // Handle keyboard navigation
  useEffect(() => {
    if (!open) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((prev) => (prev + 1) % Math.max(1, filteredItems.length));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((prev) => (prev - 1 + filteredItems.length) % Math.max(1, filteredItems.length));
      } else if (e.key === "Enter") {
        e.preventDefault();
        const selected = filteredItems[selectedIndex];
        if (selected) {
          selected.onSelect();
          onClose();
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose, filteredItems, selectedIndex]);

  // Reset selectedIndex if list shrinks
  useEffect(() => {
    if (selectedIndex >= filteredItems.length) {
      setSelectedIndex(0);
    }
  }, [filteredItems.length, selectedIndex]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-ink-950/45 p-4 pt-[12vh] backdrop-blur-xs animate-fade-in"
      onMouseDown={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
        onMouseDown={(e) => e.stopPropagation()}
        className="w-full max-w-xl rounded-2xl border border-ink-200 bg-white shadow-modal overflow-hidden animate-slide-down flex flex-col max-h-[60vh]"
      >
        {/* Search header */}
        <div className="relative flex items-center border-b border-ink-100 px-4 py-3.5 bg-white">
          <Search className="h-5 w-5 text-ink-400 shrink-0 mr-3" />
          <input
            ref={inputRef}
            aria-label="Search or type a command"
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setSelectedIndex(0);
            }}
            placeholder="Type a command or search clients, documents, tasks..."
            className="w-full bg-transparent text-sm text-ink-950 placeholder:text-ink-400 focus:outline-none"
          />
          {q && (
            <button
              onClick={() => setQ("")}
              className="p-1 text-ink-400 hover:text-ink-700 rounded-md transition-colors"
            >
              <X className="h-4 w-4" />
            </button>
          )}
          <kbd className="ml-2 hidden sm:inline-flex items-center gap-0.5 rounded border border-ink-200 bg-ink-50 px-1.5 py-0.5 text-[10px] font-medium text-ink-500">
            ESC
          </kbd>
        </div>

        {/* Results area */}
        <div className="flex-1 overflow-y-auto p-2">
          {isLoading && dq.length >= 2 && (
            <div className="px-3 py-6 text-center text-xs text-ink-500">Searching ProDesk database...</div>
          )}

          {!isLoading && filteredItems.length === 0 && (
            <div className="px-3 py-8 text-center">
              <p className="text-sm font-semibold text-ink-800">No results found</p>
              <p className="text-xs text-ink-500 mt-1">Try searching for a client name, PAN, task title, or invoice.</p>
            </div>
          )}

          {filteredItems.map((item, index) => {
            const isSelected = index === selectedIndex;
            const Icon = item.icon;
            const prevItem = filteredItems[index - 1];
            const showCategoryHeader = !prevItem || prevItem.category !== item.category;

            return (
              <div key={item.id}>
                {showCategoryHeader && (
                  <div className="px-3 pt-2.5 pb-1 text-[10px] font-bold uppercase tracking-wider text-ink-400">
                    {item.category}
                  </div>
                )}
                <button
                  type="button"
                  onClick={() => {
                    item.onSelect();
                    onClose();
                  }}
                  onMouseEnter={() => setSelectedIndex(index)}
                  className={cn(
                    "flex w-full items-center justify-between gap-3 rounded-xl px-3 py-2 text-left text-sm transition-all duration-100",
                    isSelected ? "bg-brand-50/80 text-brand-950" : "text-ink-800 hover:bg-ink-50"
                  )}
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <div
                      className={cn(
                        "flex h-7 w-7 items-center justify-center rounded-lg border shrink-0 transition-colors",
                        isSelected
                          ? "bg-brand-600 text-white border-brand-700"
                          : "bg-ink-100/70 text-ink-600 border-ink-200/60"
                      )}
                    >
                      <Icon className="h-4 w-4" />
                    </div>
                    <div className="min-w-0 truncate">
                      <span className={cn("font-medium", isSelected ? "text-brand-950" : "text-ink-900")}>
                        {item.title}
                      </span>
                      {item.subtitle && (
                        <p className="text-xs text-ink-500 truncate">{item.subtitle}</p>
                      )}
                    </div>
                  </div>
                  {isSelected && (
                    <span className="text-[11px] font-medium text-brand-700 shrink-0">Press ↵</span>
                  )}
                </button>
              </div>
            );
          })}
        </div>

        {/* Footer shortcuts */}
        <div className="flex items-center justify-between border-t border-ink-100/90 bg-ink-50/70 px-4 py-2.5 text-[11px] text-ink-500 select-none">
          <div className="flex items-center gap-3">
            <span>
              <kbd className="rounded border border-ink-200 bg-white px-1 py-0.5 font-mono text-[10px] font-semibold text-ink-700">↑↓</kbd> to navigate
            </span>
            <span>
              <kbd className="rounded border border-ink-200 bg-white px-1 py-0.5 font-mono text-[10px] font-semibold text-ink-700">↵</kbd> to select
            </span>
          </div>
          <span>ProDesk Command Center</span>
        </div>
      </div>
    </div>
  );
}

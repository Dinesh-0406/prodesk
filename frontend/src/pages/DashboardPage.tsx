import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowRight,
  Bot,
  CalendarClock,
  CheckCircle2,
  Eye,
  FileCheck2,
  FilePlus2,
  FileText,
  FolderInput,
  ListChecks,
  ListPlus,
  MessageCircle,
  Plus,
  Receipt,
  ReceiptIndianRupee,
  Sparkles,
  UserPlus,
  Users,
} from "lucide-react";
import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { Badge, Button, Card, EmptyState, Spinner, StatCard } from "../components/ui";
import { ClientFormModal } from "../features/clients/ClientForm";
import { UploadDocumentModal } from "../features/documents/UploadDocumentModal";
import { InvoiceFormModal } from "../features/invoices/InvoiceFormModal";
import { RequestFormModal } from "../features/requests/RequestFormModal";
import { TaskFormModal } from "../features/tasks/TaskFormModal";
import { useAuth } from "../hooks/useAuth";
import { documentApi, insightApi, orgApi, taskApi, whatsappApi } from "../services/endpoints";
import { cn, fmtDate, isOverdue, money } from "../utils/format";

export function DashboardPage() {
  const nav = useNavigate();
  const { me, can } = useAuth();

  const [activeModal, setActiveModal] = useState<
    "" | "new-client" | "upload-doc" | "new-task" | "new-invoice" | "request-doc"
  >("");

  const { data: org } = useQuery({
    queryKey: ["org"],
    queryFn: orgApi.current,
    enabled: can("SETTINGS_MANAGE"),
  });

  const { data: d, isLoading } = useQuery({
    queryKey: ["dashboard"],
    queryFn: insightApi.dashboard,
    refetchInterval: 60000,
  });

  // Upcoming / Open tasks
  const { data: today } = useQuery({
    queryKey: ["tasks", "dash-urgent"],
    queryFn: () => taskApi.list({ bucket: "open", sort: "due_date", page_size: 6 }),
  });

  // Overdue tasks for Attention Required
  const { data: overdueTasks } = useQuery({
    queryKey: ["tasks", "dash-overdue"],
    queryFn: () => taskApi.list({ bucket: "overdue", page_size: 4 }),
  });

  // Documents awaiting review
  const { data: review } = useQuery({
    queryKey: ["documents", "review"],
    queryFn: () => documentApi.list({ status: "UNDER_REVIEW", page_size: 5 }),
    enabled: can("DOCUMENT_APPROVE"),
  });

  // WhatsApp human handoffs
  const { data: handoffs } = useQuery({
    queryKey: ["conversations", "handoffs"],
    queryFn: () => whatsappApi.conversations({ handover_state: "HUMAN", page_size: 3 }),
    enabled: can("WHATSAPP_VIEW"),
  });

  if (org && org.onboarding_step !== "READY") {
    return <Navigate to="/onboarding" replace />;
  }

  if (isLoading || !d) {
    return <Spinner label="Loading dashboard metrics…" />;
  }

  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
  const firstName = me?.full_name.split(" ")[0] ?? "there";
  const todayFormatted = new Intl.DateTimeFormat("en-IN", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(new Date());

  const overdueCount = Number(d.overdue_tasks) || 0;
  const reviewCount = Number(d.documents_awaiting_approval) || 0;
  const handoffCount = Number(d.human_handoffs_waiting) || 0;
  const pendingDocCount = Number(d.pending_documents) || 0;

  const totalAttentionItems = overdueCount + reviewCount + handoffCount;

  return (
    <div className="space-y-6">
      {/* ----------------------------- WELCOME & OPERATIONAL HERO ----------------------------- */}
      <div className="rounded-2xl border border-ink-200/80 bg-white p-6 shadow-card">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-brand-50 px-2.5 py-0.5 text-xs font-semibold text-brand-700 border border-brand-200/60">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                Live Practice Feed
              </span>
              <span className="text-xs text-ink-500 font-medium">{todayFormatted}</span>
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-ink-950">
              {greeting}, {firstName}
            </h1>
            <p className="text-sm text-ink-600">
              Here's what requires attention across{" "}
              <span className="font-semibold text-ink-900">
                {me?.organization_name || "your firm"}
              </span>{" "}
              today.
            </p>
          </div>

          {/* Quick Action Ribbon */}
          <div className="flex flex-wrap items-center gap-2 pt-2 md:pt-0">
            {can("CLIENT_CREATE") && (
              <Button
                size="sm"
                variant="outline"
                onClick={() => setActiveModal("new-client")}
                className="gap-1.5"
              >
                <UserPlus className="h-3.5 w-3.5 text-brand-700" />
                <span>Add Client</span>
              </Button>
            )}
            {can("DOCUMENT_UPLOAD") && (
              <Button
                size="sm"
                variant="outline"
                onClick={() => setActiveModal("upload-doc")}
                className="gap-1.5"
              >
                <FilePlus2 className="h-3.5 w-3.5 text-sky-600" />
                <span>Upload Doc</span>
              </Button>
            )}
            {can("TASK_CREATE") && (
              <Button
                size="sm"
                variant="outline"
                onClick={() => setActiveModal("new-task")}
                className="gap-1.5"
              >
                <ListPlus className="h-3.5 w-3.5 text-emerald-600" />
                <span>New Task</span>
              </Button>
            )}
            {can("INVOICE_CREATE") && (
              <Button
                size="sm"
                variant="outline"
                onClick={() => setActiveModal("new-invoice")}
                className="gap-1.5"
              >
                <ReceiptIndianRupee className="h-3.5 w-3.5 text-amber-600" />
                <span>Invoice</span>
              </Button>
            )}
            {can("DOCUMENT_REQUEST_CREATE") && (
              <Button
                size="sm"
                variant="primary"
                onClick={() => setActiveModal("request-doc")}
                className="gap-1.5 shadow-sm"
              >
                <FolderInput className="h-3.5 w-3.5" />
                <span>Request Docs</span>
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* ----------------------------- KEY METRICS GRID ----------------------------- */}
      <div className="grid grid-cols-2 gap-3.5 md:grid-cols-3 xl:grid-cols-6">
        <StatCard
          label="Active Clients"
          value={d.active_clients}
          hint={`${d.total_clients} total`}
          icon={Users}
          onClick={() => nav("/clients")}
        />

        <StatCard
          label="Pending Docs"
          value={d.pending_documents}
          tone={pendingDocCount > 0 ? "warn" : "default"}
          hint="From client requests"
          icon={FolderInput}
          onClick={() => nav("/document-requests")}
        />

        <StatCard
          label="Open Tasks"
          value={d.open_tasks}
          hint={overdueCount > 0 ? `${overdueCount} overdue` : "In progress"}
          icon={ListChecks}
          onClick={() => nav("/tasks")}
        />

        <StatCard
          label="Overdue Tasks"
          value={d.overdue_tasks}
          tone={overdueCount > 0 ? "danger" : "default"}
          hint={overdueCount > 0 ? "Urgent attention" : "All on schedule"}
          icon={AlertTriangle}
          onClick={() => nav("/tasks?bucket=overdue")}
        />

        <StatCard
          label="Receivables"
          value={money(d.outstanding_amount)}
          hint={`${d.pending_invoices} pending invoices`}
          tone={Number(d.outstanding_amount) > 0 ? "warn" : "good"}
          icon={Receipt}
          onClick={() => nav("/invoices")}
        />

        <StatCard
          label="WhatsApp Inbox"
          value={d.whatsapp_conversations}
          hint={handoffCount > 0 ? `${handoffCount} waiting for person` : "Active threads"}
          tone={handoffCount > 0 ? "warn" : "default"}
          icon={MessageCircle}
          onClick={() => nav("/whatsapp")}
        />
      </div>

      {/* ----------------------------- ATTENTION REQUIRED COMPONENT ----------------------------- */}
      {totalAttentionItems > 0 && (
        <div className="rounded-2xl border border-rose-200/90 bg-rose-50/40 p-5 shadow-card">
          <div className="flex items-center justify-between border-b border-rose-200/70 pb-3 mb-4">
            <div className="flex items-center gap-2.5">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-rose-600 text-white shadow-2xs">
                <AlertTriangle className="h-4 w-4" />
              </div>
              <div>
                <h2 className="text-sm font-bold text-rose-950 tracking-tight">Attention Required</h2>
                <p className="text-xs text-rose-700">
                  {totalAttentionItems} items requiring urgent response or sign-off
                </p>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            {/* 1. Overdue tasks */}
            {overdueCount > 0 && (
              <div className="rounded-xl border border-rose-200 bg-white p-3.5 shadow-2xs flex flex-col justify-between">
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-rose-800 uppercase tracking-wide">
                      Overdue Tasks
                    </span>
                    <Badge value="OVERDUE" color="red" label={`${overdueCount} overdue`} />
                  </div>
                  <ul className="space-y-1 mt-2 text-xs">
                    {overdueTasks?.items.slice(0, 3).map((t) => (
                      <li key={t.id} className="truncate text-ink-800">
                        <span className="font-semibold text-ink-950">{t.client.name}</span>: {t.title}
                      </li>
                    ))}
                  </ul>
                </div>
                <Button
                  size="xs"
                  variant="subtle"
                  onClick={() => nav("/tasks?bucket=overdue")}
                  className="mt-3 w-full justify-between"
                >
                  <span>Resolve overdue tasks</span>
                  <ArrowRight className="h-3 w-3" />
                </Button>
              </div>
            )}

            {/* 2. Review queue */}
            {reviewCount > 0 && can("DOCUMENT_APPROVE") && (
              <div className="rounded-xl border border-violet-200 bg-white p-3.5 shadow-2xs flex flex-col justify-between">
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-violet-800 uppercase tracking-wide">
                      Review Queue
                    </span>
                    <Badge value="UNDER_REVIEW" color="violet" label={`${reviewCount} awaiting sign-off`} />
                  </div>
                  <ul className="space-y-1 mt-2 text-xs">
                    {review?.items.slice(0, 3).map((doc) => (
                      <li key={doc.id} className="truncate text-ink-800">
                        <span className="font-semibold text-ink-950">{doc.client.name}</span>: {doc.file_name}
                      </li>
                    ))}
                  </ul>
                </div>
                <Button
                  size="xs"
                  variant="subtle"
                  onClick={() => nav("/documents?status=UNDER_REVIEW")}
                  className="mt-3 w-full justify-between text-violet-800 bg-violet-50 hover:bg-violet-100 border-violet-200"
                >
                  <span>Review & approve documents</span>
                  <ArrowRight className="h-3 w-3" />
                </Button>
              </div>
            )}

            {/* 3. WhatsApp human handoff */}
            {handoffCount > 0 && can("WHATSAPP_VIEW") && (
              <div className="rounded-xl border border-amber-200 bg-white p-3.5 shadow-2xs flex flex-col justify-between">
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-amber-800 uppercase tracking-wide">
                      WhatsApp Handoff
                    </span>
                    <Badge value="HUMAN_REQUESTED" color="amber" label={`${handoffCount} wants human`} />
                  </div>
                  <ul className="space-y-1 mt-2 text-xs">
                    {handoffs?.items.slice(0, 3).map((c) => (
                      <li key={c.id} className="truncate text-ink-800">
                        <span className="font-semibold text-ink-950">
                          {c.client?.name ?? c.contact.profile_name ?? c.contact.wa_id}
                        </span>
                        : {c.last_message_preview || "Requested staff assistance"}
                      </li>
                    ))}
                  </ul>
                </div>
                <Button
                  size="xs"
                  variant="subtle"
                  onClick={() => nav("/whatsapp")}
                  className="mt-3 w-full justify-between text-amber-800 bg-amber-50 hover:bg-amber-100 border-amber-200"
                >
                  <span>Open WhatsApp conversations</span>
                  <ArrowRight className="h-3 w-3" />
                </Button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ----------------------------- COMPOSED OPERATIONAL SECTIONS ----------------------------- */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Work Requiring Attention / Upcoming Work */}
        <Card
          title="Upcoming & Open Work"
          subtitle="Tasks ordered by filing and client deadlines"
          actions={
            <Link
              to="/tasks"
              className="inline-flex items-center gap-1 text-xs font-semibold text-brand-700 hover:text-brand-900 transition-colors"
            >
              <span>View all tasks</span>
              <ArrowRight className="h-3 w-3" />
            </Link>
          }
          padded={false}
        >
          {!today?.items.length ? (
            <EmptyState
              title="No open tasks"
              hint="All assigned tasks are completed or up to date."
              action={
                <Button size="sm" variant="outline" onClick={() => setActiveModal("new-task")}>
                  <Plus className="h-3.5 w-3.5" />
                  <span>Create new task</span>
                </Button>
              }
            />
          ) : (
            <ul className="divide-y divide-ink-100/80">
              {today.items.map((t) => {
                const overdue = isOverdue(t.due_date);
                return (
                  <li
                    key={t.id}
                    className="flex items-center justify-between gap-3 px-5 py-3 hover:bg-ink-50/60 transition-colors"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <Link
                          to={`/clients/${t.client_id}`}
                          className="font-semibold text-xs text-ink-950 hover:text-brand-700 truncate"
                        >
                          {t.client.name}
                        </Link>
                        <span className="text-[11px] text-ink-400">·</span>
                        <span className="text-xs text-ink-600 truncate">{t.title}</span>
                      </div>
                      <div className="mt-1 flex items-center gap-2 text-[11px] text-ink-500">
                        <span className="font-medium text-ink-600">{t.service_type}</span>
                        <span>·</span>
                        <span>{t.assigned_employee?.full_name ?? "Unassigned"}</span>
                        {t.financial_year && (
                          <>
                            <span>·</span>
                            <span>FY {t.financial_year}</span>
                          </>
                        )}
                      </div>
                    </div>

                    <div className="flex shrink-0 items-center gap-3">
                      <div className="text-right">
                        <span
                          className={cn(
                            "block text-xs font-medium tabular-nums",
                            overdue ? "text-rose-700 font-semibold" : "text-ink-600"
                          )}
                        >
                          {fmtDate(t.due_date)}
                        </span>
                        {overdue && (
                          <span className="block text-[10px] text-rose-600 font-medium">Overdue</span>
                        )}
                      </div>
                      <Badge value={t.status} />
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>

        {/* Documents Awaiting Approval / Review Queue */}
        {can("DOCUMENT_APPROVE") ? (
          <Card
            title="Documents Awaiting Review"
            subtitle="Uploaded by staff; requires sign-off before client delivery"
            actions={
              <Link
                to="/documents?status=UNDER_REVIEW"
                className="inline-flex items-center gap-1 text-xs font-semibold text-brand-700 hover:text-brand-900 transition-colors"
              >
                <span>Full queue</span>
                <ArrowRight className="h-3 w-3" />
              </Link>
            }
            padded={false}
          >
            {!review?.items.length ? (
              <EmptyState
                title="Review queue is clear"
                hint="Prepared client documents submitted for approval will appear here."
                icon={FileCheck2}
              />
            ) : (
              <ul className="divide-y divide-ink-100/80">
                {review.items.map((doc) => (
                  <li
                    key={doc.id}
                    className="flex items-center justify-between gap-3 px-5 py-3 hover:bg-ink-50/60 transition-colors"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-xs font-semibold text-ink-950">{doc.file_name}</p>
                      <div className="mt-0.5 flex items-center gap-2 text-[11px] text-ink-500">
                        <Link
                          to={`/clients/${doc.client_id}`}
                          className="font-medium text-brand-700 hover:underline truncate"
                        >
                          {doc.client.name}
                        </Link>
                        <span>·</span>
                        <span>{doc.financial_year ? `FY ${doc.financial_year}` : doc.document_type}</span>
                        <span>·</span>
                        <span>v{doc.version}</span>
                      </div>
                    </div>

                    <div className="flex shrink-0 items-center gap-2">
                      <Button
                        size="xs"
                        variant="secondary"
                        onClick={() => nav(`/documents/${doc.id}`)}
                        className="gap-1 text-xs"
                      >
                        <Eye className="h-3.5 w-3.5" />
                        <span>Review</span>
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        ) : (
          /* Fallback for non-approvers: Quick Navigation & Practice Shortcuts */
          <Card title="Quick Navigation" subtitle="Essential workflows for your daily client operations">
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => nav("/clients")}
                className="flex items-center gap-3 p-3 rounded-xl border border-ink-200/80 hover:border-brand-300 hover:bg-brand-50/30 transition-all text-left"
              >
                <div className="h-8 w-8 rounded-lg bg-brand-100 text-brand-700 flex items-center justify-center">
                  <Users className="h-4 w-4" />
                </div>
                <div>
                  <p className="text-xs font-semibold text-ink-950">Clients Directory</p>
                  <p className="text-[11px] text-ink-500">Manage client relationships</p>
                </div>
              </button>

              <button
                type="button"
                onClick={() => nav("/documents")}
                className="flex items-center gap-3 p-3 rounded-xl border border-ink-200/80 hover:border-sky-300 hover:bg-sky-50/30 transition-all text-left"
              >
                <div className="h-8 w-8 rounded-lg bg-sky-100 text-sky-700 flex items-center justify-center">
                  <FileText className="h-4 w-4" />
                </div>
                <div>
                  <p className="text-xs font-semibold text-ink-950">Document Vault</p>
                  <p className="text-[11px] text-ink-500">Secure private files</p>
                </div>
              </button>

              <button
                type="button"
                onClick={() => nav("/compliance")}
                className="flex items-center gap-3 p-3 rounded-xl border border-ink-200/80 hover:border-amber-300 hover:bg-amber-50/30 transition-all text-left"
              >
                <div className="h-8 w-8 rounded-lg bg-amber-100 text-amber-700 flex items-center justify-center">
                  <CalendarClock className="h-4 w-4" />
                </div>
                <div>
                  <p className="text-xs font-semibold text-ink-950">Compliance</p>
                  <p className="text-[11px] text-ink-500">Tax & ROC deadlines</p>
                </div>
              </button>

              <button
                type="button"
                onClick={() => nav("/assistant")}
                className="flex items-center gap-3 p-3 rounded-xl border border-ink-200/80 hover:border-purple-300 hover:bg-purple-50/30 transition-all text-left"
              >
                <div className="h-8 w-8 rounded-lg bg-purple-100 text-purple-700 flex items-center justify-center">
                  <Sparkles className="h-4 w-4" />
                </div>
                <div>
                  <p className="text-xs font-semibold text-ink-950">AI Assistant</p>
                  <p className="text-[11px] text-ink-500">Ask practice questions</p>
                </div>
              </button>
            </div>
          </Card>
        )}
      </div>

      {/* ----------------------------- RECENT QUICK SHORTCUTS ----------------------------- */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-xl border border-ink-200/80 bg-white p-4 shadow-card flex items-center justify-between">
          <div>
            <span className="text-[11px] font-semibold text-ink-500 uppercase tracking-wider block">
              Deliveries
            </span>
            <span className="text-xl font-bold text-ink-950 tabular-nums">
              {d.documents_delivered}
            </span>
            <span className="text-[11px] text-ink-500 block">Sent over WhatsApp</span>
          </div>
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600">
            <CheckCircle2 className="h-5 w-5" />
          </div>
        </div>

        <div className="rounded-xl border border-ink-200/80 bg-white p-4 shadow-card flex items-center justify-between">
          <div>
            <span className="text-[11px] font-semibold text-ink-500 uppercase tracking-wider block">
              Upcoming Deadlines
            </span>
            <span className="text-xl font-bold text-ink-950 tabular-nums">
              {d.upcoming_deadlines}
            </span>
            <span className="text-[11px] text-ink-500 block">Next 30 days</span>
          </div>
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-sky-50 text-sky-600">
            <CalendarClock className="h-5 w-5" />
          </div>
        </div>

        <div className="rounded-xl border border-ink-200/80 bg-white p-4 shadow-card flex items-center justify-between">
          <div>
            <span className="text-[11px] font-semibold text-ink-500 uppercase tracking-wider block">
              Pending Invoices
            </span>
            <span className="text-xl font-bold text-ink-950 tabular-nums">
              {d.pending_invoices}
            </span>
            <span className="text-[11px] text-ink-500 block">Unpaid client bills</span>
          </div>
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-50 text-amber-600">
            <Receipt className="h-5 w-5" />
          </div>
        </div>

        <div className="rounded-xl border border-ink-200/80 bg-white p-4 shadow-card flex items-center justify-between">
          <div>
            <span className="text-[11px] font-semibold text-ink-500 uppercase tracking-wider block">
              AI Query Assistant
            </span>
            <span className="text-xs font-semibold text-brand-700 block mt-1">Instant Answers</span>
            <span className="text-[11px] text-ink-500 block">From verified records</span>
          </div>
          <button
            type="button"
            onClick={() => nav("/assistant")}
            aria-label="Ask assistant"
            className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-50 text-brand-700 hover:bg-brand-100 transition-colors"
          >
            <Bot className="h-5 w-5" />
          </button>
        </div>
      </div>

      {/* Global Modals triggered from dashboard */}
      <ClientFormModal
        open={activeModal === "new-client"}
        onClose={() => setActiveModal("")}
        onSaved={(c) => nav(`/clients/${c.id}`)}
      />
      <UploadDocumentModal
        open={activeModal === "upload-doc"}
        onClose={() => setActiveModal("")}
        onUploaded={(doc) => nav(`/documents/${doc.id}`)}
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

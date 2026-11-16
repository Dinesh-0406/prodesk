import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  FilePlus2,
  FolderInput,
  History,
  ListPlus,
  Mail,
  MapPin,
  MessageCircle,
  Pencil,
  Phone,
  ReceiptIndianRupee,
  Send,
  UserCheck,
} from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Avatar, Badge, Button, Card, EmptyState, KeyValue, Spinner, Table, Tabs } from "../components/ui";
import { ClientFormModal } from "../features/clients/ClientForm";
import { UploadDocumentModal } from "../features/documents/UploadDocumentModal";
import { InvoiceFormModal } from "../features/invoices/InvoiceFormModal";
import { RequestFormModal } from "../features/requests/RequestFormModal";
import { TaskFormModal } from "../features/tasks/TaskFormModal";
import { Can, useAuth } from "../hooks/useAuth";
import { useToast } from "../hooks/useToast";
import { errorMessage } from "../services/api";
import { billingApi, clientApi, documentApi, taskApi, whatsappApi } from "../services/endpoints";
import type { Doc, Invoice, Task } from "../types";
import { fmtDate, fmtDateTime, humanize, isOverdue, money } from "../utils/format";

export function ClientDetailPage() {
  const { id = "" } = useParams();
  const nav = useNavigate();
  const qc = useQueryClient();
  const toast = useToast();
  const { can } = useAuth();
  const [tab, setTab] = useState("overview");
  const [modal, setModal] = useState<"" | "edit" | "upload" | "request" | "task" | "invoice">("");

  const { data: s, isLoading } = useQuery({
    queryKey: ["client-summary", id],
    queryFn: () => clientApi.summary(id),
  });

  const docs = useQuery({
    queryKey: ["documents", "client", id],
    queryFn: () => documentApi.list({ client_id: id, page_size: 50 }),
    enabled: tab === "documents",
  });

  const tasks = useQuery({
    queryKey: ["tasks", "client", id],
    queryFn: () =>
      taskApi.list({
        client_id: id,
        page_size: 50,
        sort: "created_at",
        order: "desc",
      }),
    enabled: tab === "tasks",
  });

  const invoices = useQuery({
    queryKey: ["invoices", "client", id],
    queryFn: () => billingApi.invoices({ client_id: id }),
    enabled: tab === "invoices" && can("INVOICE_VIEW"),
  });

  const timeline = useQuery({
    queryKey: ["client-timeline", id],
    queryFn: () => clientApi.timeline(id),
    enabled: tab === "history",
  });

  const convs = useQuery({
    queryKey: ["conversations", "client", s?.client.phone],
    queryFn: () => whatsappApi.conversations({ q: s?.client.name }),
    enabled: tab === "communication" && can("WHATSAPP_VIEW") && !!s,
  });

  const conv = convs.data?.items.find((c) => c.client_id === id);

  const messages = useQuery({
    queryKey: ["messages", conv?.id],
    queryFn: () => whatsappApi.messages(conv!.id),
    enabled: !!conv,
  });

  const welcome = useMutation({
    mutationFn: () => clientApi.sendWelcome(id),
    onSuccess: () => toast("success", "Welcome message queued for WhatsApp delivery"),
    onError: (e) => toast("error", errorMessage(e)),
  });

  if (isLoading || !s) {
    return <Spinner label="Loading client workspace…" />;
  }

  const c = s.client;

  return (
    <div className="space-y-6">
      {/* ----------------------------- CRM PROFILE HEADER ----------------------------- */}
      <div className="rounded-2xl border border-ink-200/80 bg-white p-6 shadow-card">
        <div className="flex flex-col gap-5 md:flex-row md:items-start md:justify-between">
          <div className="flex items-start gap-4 min-w-0">
            <Avatar name={c.name} size="xl" className="shadow-xs shrink-0 mt-0.5" />
            <div className="min-w-0 space-y-1.5">
              <div className="flex flex-wrap items-center gap-2.5">
                <h1 className="text-2xl font-bold tracking-tight text-ink-950 truncate">{c.name}</h1>
                <Badge value={c.status} />
                <Badge value={s.whatsapp_status} />
              </div>

              <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-ink-600 font-medium">
                <span className="flex items-center gap-1.5 font-mono">
                  <Phone className="h-3.5 w-3.5 text-ink-400" />
                  {c.phone}
                </span>
                {c.email && (
                  <span className="flex items-center gap-1.5 truncate">
                    <Mail className="h-3.5 w-3.5 text-ink-400" />
                    {c.email}
                  </span>
                )}
                <span className="text-ink-700 bg-ink-100/70 px-2 py-0.5 rounded text-[11px]">
                  {humanize(c.client_type)}
                </span>
                {c.pan && (
                  <span className="font-mono text-ink-800 bg-ink-50 border border-ink-200/80 px-2 py-0.5 rounded text-[11px]">
                    PAN: {c.pan}
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Action Toolbar */}
          <div className="flex flex-wrap items-center gap-2 pt-1">
            <Can perm="CLIENT_UPDATE">
              <Button variant="secondary" size="sm" onClick={() => setModal("edit")} className="gap-1.5">
                <Pencil className="h-3.5 w-3.5" />
                <span>Edit</span>
              </Button>
            </Can>
            <Can perm="DOCUMENT_UPLOAD">
              <Button variant="secondary" size="sm" onClick={() => setModal("upload")} className="gap-1.5">
                <FilePlus2 className="h-3.5 w-3.5" />
                <span>Upload</span>
              </Button>
            </Can>
            <Can perm="DOCUMENT_REQUEST_CREATE">
              <Button variant="secondary" size="sm" onClick={() => setModal("request")} className="gap-1.5">
                <FolderInput className="h-3.5 w-3.5" />
                <span>Request docs</span>
              </Button>
            </Can>
            <Can perm="TASK_CREATE">
              <Button variant="secondary" size="sm" onClick={() => setModal("task")} className="gap-1.5">
                <ListPlus className="h-3.5 w-3.5" />
                <span>Task</span>
              </Button>
            </Can>
            <Can perm="INVOICE_CREATE">
              <Button variant="secondary" size="sm" onClick={() => setModal("invoice")} className="gap-1.5">
                <ReceiptIndianRupee className="h-3.5 w-3.5" />
                <span>Invoice</span>
              </Button>
            </Can>
          </div>
        </div>
      </div>

      {/* ----------------------------- TABS NAVIGATION ----------------------------- */}
      <Tabs
        value={tab}
        onChange={setTab}
        tabs={[
          { value: "overview", label: "Overview" },
          { value: "documents", label: "Documents", count: s.counts.documents },
          { value: "tasks", label: "Tasks", count: s.counts.open_tasks },
          { value: "invoices", label: "Invoices", count: s.counts.invoices },
          { value: "communication", label: "WhatsApp", count: s.counts.messages },
          { value: "history", label: "History" },
        ]}
      />

      {/* ----------------------------- TAB CONTENTS ----------------------------- */}
      <div>
        {tab === "overview" && (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            {/* Pending Work Column */}
            <div className="space-y-6 lg:col-span-2">
              <Card
                title="Active & Pending Work"
                subtitle="Tasks, open filings, and document requests awaiting client submission"
                padded={false}
              >
                {!s.open_tasks.length && !s.pending_requests.length ? (
                  <EmptyState title="Nothing pending for this client" hint="All tasks and document requests are complete." />
                ) : (
                  <ul className="divide-y divide-ink-100/80">
                    {s.pending_requests.map((r) => (
                      <li key={r.id} className="flex items-center justify-between gap-3 px-5 py-3.5 hover:bg-ink-50/50">
                        <div className="min-w-0 flex-1">
                          <p className="text-xs font-semibold text-ink-950">
                            Waiting on client: {r.title}
                          </p>
                          <p className="text-[11px] text-ink-500 mt-0.5 truncate">
                            Needed: {r.pending_items.join(", ")}
                          </p>
                        </div>
                        <div className="flex shrink-0 items-center gap-3">
                          <span className="text-xs text-ink-500 tabular-nums">
                            Due {fmtDate(r.due_date)}
                          </span>
                          <Badge value={r.status} />
                        </div>
                      </li>
                    ))}
                    {s.open_tasks.map((t) => (
                      <li key={t.id} className="flex items-center justify-between gap-3 px-5 py-3.5 hover:bg-ink-50/50">
                        <div className="min-w-0 flex-1">
                          <p className="text-xs font-semibold text-ink-950">{t.title}</p>
                          <p className="text-[11px] text-ink-500 mt-0.5">{t.service_type}</p>
                        </div>
                        <div className="flex shrink-0 items-center gap-3">
                          <span
                            className={`text-xs tabular-nums font-medium ${
                              isOverdue(t.due_date) ? "text-rose-700" : "text-ink-500"
                            }`}
                          >
                            Due {fmtDate(t.due_date)}
                          </span>
                          <Badge value={t.status} />
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>

              {/* Financial & Activity Snapshot */}
              <div className="grid grid-cols-2 gap-4">
                <div className="rounded-xl border border-ink-200/80 bg-white p-4 shadow-card">
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-ink-500 block">
                    Outstanding Balance
                  </span>
                  <span className="text-2xl font-bold text-ink-950 tabular-nums block mt-1">
                    {money(s.outstanding_amount)}
                  </span>
                  <span className="text-xs text-ink-500 block mt-1">
                    {s.counts.invoices ? `${s.counts.invoices} total invoices` : "No open invoices"}
                  </span>
                </div>

                <div className="rounded-xl border border-ink-200/80 bg-white p-4 shadow-card">
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-ink-500 block">
                    WhatsApp Activity
                  </span>
                  <span className="text-xs font-semibold text-ink-800 block mt-2">
                    {s.last_message_at ? `Last active ${fmtDateTime(s.last_message_at)}` : "No messages yet"}
                  </span>
                  <span className="text-[11px] text-ink-500 block mt-1">
                    {s.counts.messages} message(s) logged
                  </span>
                </div>
              </div>
            </div>

            {/* Client Profile Card */}
            <div className="space-y-4">
              <Card title="Client Details">
                <KeyValue
                  items={[
                    ["Email", c.email],
                    ["GSTIN", c.gstin],
                    [
                      "Assigned To",
                      c.assigned_employee ? (
                        <span className="flex items-center gap-1.5 text-xs text-ink-900 font-medium">
                          <UserCheck className="h-3.5 w-3.5 text-brand-600" />
                          {c.assigned_employee.full_name}
                        </span>
                      ) : (
                        "Unassigned"
                      ),
                    ],
                    ["Outstanding", money(s.outstanding_amount)],
                    ["Last WhatsApp", fmtDateTime(s.last_message_at)],
                    [
                      "Address",
                      c.address ? (
                        <span className="flex items-start gap-1 text-xs">
                          <MapPin className="h-3.5 w-3.5 text-ink-400 shrink-0 mt-0.5" />
                          {c.address}
                        </span>
                      ) : null,
                    ],
                  ]}
                />

                {c.notes && (
                  <div className="mt-4 rounded-lg bg-ink-50/70 border border-ink-100 p-3 text-xs text-ink-700">
                    <p className="font-semibold text-ink-900 mb-1">Notes</p>
                    <p className="leading-relaxed">{c.notes}</p>
                  </div>
                )}

                <Can perm="WHATSAPP_SEND">
                  {s.whatsapp_status === "OPTED_IN" && (
                    <Button
                      size="sm"
                      variant="subtle"
                      className="mt-4 w-full justify-center gap-1.5"
                      loading={welcome.isPending}
                      onClick={() => welcome.mutate()}
                    >
                      <MessageCircle className="h-4 w-4" />
                      <span>Send welcome message</span>
                    </Button>
                  )}
                </Can>
              </Card>
            </div>
          </div>
        )}

        {tab === "documents" && (
          <Card padded={false} className="border border-ink-200/80 shadow-card">
            {docs.isLoading ? (
              <Spinner label="Loading client documents…" />
            ) : (
              <Table<Doc>
                rows={docs.data?.items ?? []}
                onRowClick={(d) => nav(`/documents/${d.id}`)}
                empty={<EmptyState title="No documents in client vault" />}
                columns={[
                  {
                    key: "f",
                    header: "Document File",
                    render: (d) => <span className="font-semibold text-xs text-ink-950">{d.file_name}</span>,
                  },
                  {
                    key: "t",
                    header: "Type",
                    render: (d) => <span className="text-xs text-ink-700">{humanize(d.document_type)}</span>,
                  },
                  {
                    key: "fy",
                    header: "Financial Year",
                    render: (d) => <span className="text-xs text-ink-600">{d.financial_year ?? "—"}</span>,
                  },
                  {
                    key: "v",
                    header: "Version",
                    render: (d) => (
                      <span className="font-mono text-xs bg-ink-100/70 px-1.5 py-0.5 rounded text-ink-700">
                        v{d.version}
                      </span>
                    ),
                  },
                  {
                    key: "src",
                    header: "Source",
                    render: (d) => <span className="text-xs text-ink-600">{humanize(d.source)}</span>,
                  },
                  {
                    key: "s",
                    header: "Status",
                    render: (d) => <Badge value={d.status} />,
                  },
                ]}
              />
            )}
          </Card>
        )}

        {tab === "tasks" && (
          <Card padded={false} className="border border-ink-200/80 shadow-card">
            <Table<Task>
              rows={tasks.data?.items ?? []}
              onRowClick={() => nav(`/tasks?client=${id}`)}
              empty={<EmptyState title="No tasks for this client" />}
              columns={[
                {
                  key: "t",
                  header: "Task Title",
                  render: (t) => <span className="font-semibold text-xs text-ink-950">{t.title}</span>,
                },
                {
                  key: "svc",
                  header: "Service Type",
                  render: (t) => <span className="text-xs text-ink-700">{t.service_type}</span>,
                },
                {
                  key: "due",
                  header: "Due Date",
                  render: (t) => (
                    <span
                      className={`text-xs tabular-nums font-medium ${
                        isOverdue(t.due_date) ? "text-rose-700" : "text-ink-600"
                      }`}
                    >
                      {fmtDate(t.due_date)}
                    </span>
                  ),
                },
                {
                  key: "s",
                  header: "Status",
                  render: (t) => <Badge value={t.status} />,
                },
              ]}
            />
          </Card>
        )}

        {tab === "invoices" && (
          <Card padded={false} className="border border-ink-200/80 shadow-card">
            <Table<Invoice>
              rows={invoices.data?.items ?? []}
              onRowClick={(i) => nav(`/invoices?open=${i.id}`)}
              empty={<EmptyState title="No invoices for this client" />}
              columns={[
                {
                  key: "n",
                  header: "Invoice Number",
                  render: (i) => <span className="font-semibold text-xs text-ink-950">{i.invoice_number}</span>,
                },
                {
                  key: "d",
                  header: "Issue Date",
                  render: (i) => <span className="text-xs text-ink-600">{fmtDate(i.issue_date)}</span>,
                },
                {
                  key: "t",
                  header: "Total Amount",
                  render: (i) => <span className="text-xs font-semibold tabular-nums">{money(i.total)}</span>,
                },
                {
                  key: "b",
                  header: "Balance Due",
                  render: (i) => (
                    <span
                      className={`text-xs font-semibold tabular-nums ${
                        Number(i.balance_due) > 0 ? "text-rose-700" : "text-emerald-700"
                      }`}
                    >
                      {money(i.balance_due)}
                    </span>
                  ),
                },
                {
                  key: "s",
                  header: "Status",
                  render: (i) => <Badge value={i.status} />,
                },
              ]}
            />
          </Card>
        )}

        {tab === "communication" && (
          <Card
            title="WhatsApp Communication Thread"
            subtitle="Verified official WhatsApp conversation history"
            actions={
              conv && (
                <Link
                  className="inline-flex items-center gap-1 text-xs font-semibold text-brand-700 hover:text-brand-900"
                  to={`/whatsapp?conversation=${conv.id}`}
                >
                  <span>Open in WhatsApp Inbox</span>
                  <Send className="h-3 w-3" />
                </Link>
              )
            }
          >
            {!conv ? (
              <EmptyState title="No WhatsApp conversation on record yet" />
            ) : (
              <div className="space-y-3 max-h-[500px] overflow-y-auto p-2">
                {messages.data?.items.map((m) => (
                  <div
                    key={m.id}
                    className={`flex ${m.direction === "INBOUND" ? "justify-start" : "justify-end"}`}
                  >
                    <div
                      className={`max-w-[70%] rounded-xl px-4 py-2.5 text-xs shadow-2xs ${
                        m.direction === "INBOUND"
                          ? "bg-ink-100/90 text-ink-900"
                          : "bg-brand-50 border border-brand-200/80 text-brand-950"
                      }`}
                    >
                      <p className="whitespace-pre-wrap leading-relaxed">{m.body}</p>
                      <p className="mt-1 text-[10px] text-ink-400">
                        {humanize(m.sender)} · {fmtDateTime(m.timestamp)} · {humanize(m.status)}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        )}

        {tab === "history" && (
          <Card title="Activity & Audit History" padded={false} className="border border-ink-200/80 shadow-card">
            {!timeline.data?.length ? (
              <EmptyState title="No activity recorded" icon={History} />
            ) : (
              <ul className="divide-y divide-ink-100/80">
                {timeline.data?.map((t, i) => (
                  <li key={i} className="flex items-center justify-between px-5 py-3 text-xs">
                    <span className="font-semibold text-ink-900">{humanize(t.action)}</span>
                    <span className="text-ink-500">
                      {humanize(t.actor_type)} · {fmtDateTime(t.timestamp)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        )}
      </div>

      {/* Modals */}
      {modal === "edit" && (
        <ClientFormModal
          open
          client={c}
          onClose={() => {
            setModal("");
            qc.invalidateQueries({ queryKey: ["client-summary", id] });
          }}
        />
      )}
      {modal === "upload" && (
        <UploadDocumentModal
          open
          clientId={id}
          onClose={() => setModal("")}
          onUploaded={(d) => nav(`/documents/${d.id}`)}
        />
      )}
      {modal === "request" && <RequestFormModal open clientId={id} onClose={() => setModal("")} />}
      {modal === "task" && <TaskFormModal open clientId={id} onClose={() => setModal("")} />}
      {modal === "invoice" && <InvoiceFormModal open clientId={id} onClose={() => setModal("")} />}
    </div>
  );
}

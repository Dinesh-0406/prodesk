import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FlaskConical, Search } from "lucide-react";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Avatar, Badge, Button, Card, EmptyState, Input, Modal, PageHeader, Select, Spinner } from "../components/ui";
import { MessageThread } from "../features/whatsapp/MessageThread";
import { useDebounce } from "../hooks/useDebounce";
import { useToast } from "../hooks/useToast";
import { errorMessage } from "../services/api";
import { clientApi, documentApi, taskApi, whatsappApi } from "../services/endpoints";
import { cn, fmtDate, humanize, timeAgo } from "../utils/format";

function Simulator({ open, onClose }: { open: boolean; onClose: () => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [phone, setPhone] = useState("9876500001");
  const [text, setText] = useState("Mera ITR status kya hai?");
  const [file, setFile] = useState<File | null>(null);

  const m = useMutation({
    mutationFn: async () => {
      if (file) {
        const b64 = await new Promise<string>((res) => {
          const r = new FileReader();
          r.onload = () => res(String(r.result).split(",")[1]);
          r.readAsDataURL(file);
        });
        return whatsappApi.simulate({
          phone,
          media_base64: b64,
          media_mime: file.type || "application/pdf",
          media_filename: file.name,
        });
      }
      return whatsappApi.simulate({ phone, text });
    },
    onSuccess: () => {
      toast("success", "Simulated WhatsApp message dispatched through webhook pipeline");
      setTimeout(() => qc.invalidateQueries({ queryKey: ["conversations"] }), 600);
      onClose();
    },
    onError: (e) => toast("error", errorMessage(e)),
  });

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Simulate Inbound WhatsApp Message"
      subtitle="Development sandbox. Posts signed payload to webhook worker."
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Close
          </Button>
          <Button loading={m.isPending} onClick={() => m.mutate()} className="shadow-sm">
            Send as client
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <p className="rounded-lg bg-amber-50 border border-amber-200 p-2.5 text-xs text-amber-900 leading-relaxed">
          Development only. The message is signed and delivered to the real webhook, then classified and processed by the background Celery worker.
        </p>

        <Input
          label="Client phone"
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          placeholder="98765 00001"
        />

        <Select
          label="Try a sample"
          options={[
            "Mera ITR status kya hai?",
            "Mujhe pichle saal ki balance sheet bhejo",
            "Mere kaunse documents pending hain?",
            "Mera GST status kya hai?",
            "Invoice bhejo",
            "Mera payment kitna pending hai?",
            "Document upload karna hai",
            "CA se baat karni hai",
            "What are your office timings?",
            "STOP",
          ].map((s) => ({ value: s, label: s }))}
          value={text}
          onChange={(e) => setText(e.target.value)}
        />

        <Input
          label="Message"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Type message text..."
        />

        <div className="space-y-1">
          <p className="text-xs font-semibold text-ink-700">…or attach a document</p>
          <input
            type="file"
            aria-label="Attachment"
            className="text-xs text-ink-700 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-brand-50 file:text-brand-700 hover:file:bg-brand-100 cursor-pointer"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </div>
      </div>
    </Modal>
  );
}

function ClientContextPanel({ clientId }: { clientId: string }) {
  const { data: summary } = useQuery({
    queryKey: ["client-summary", clientId],
    queryFn: () => clientApi.summary(clientId),
  });

  const { data: openTasks } = useQuery({
    queryKey: ["tasks", "client-context", clientId],
    queryFn: () => taskApi.list({ client_id: clientId, bucket: "open", page_size: 4 }),
  });

  const { data: recentDocs } = useQuery({
    queryKey: ["documents", "client-context", clientId],
    queryFn: () => documentApi.list({ client_id: clientId, page_size: 3 }),
  });

  if (!summary) return null;
  const c = summary.client;

  return (
    <div className="hidden xl:flex w-72 flex-col border-l border-ink-100/90 bg-white p-4 space-y-4 overflow-y-auto text-xs">
      <div className="border-b border-ink-100 pb-3">
        <div className="flex items-center gap-2 mb-2">
          <Avatar name={c.name} size="sm" />
          <div className="min-w-0">
            <Link
              to={`/clients/${c.id}`}
              className="font-semibold text-xs text-ink-950 hover:text-brand-700 truncate block"
            >
              {c.name}
            </Link>
            <span className="text-[11px] text-ink-500 font-mono">+{c.phone}</span>
          </div>
        </div>
        <div className="flex items-center gap-1.5 mt-2">
          <Badge value={c.status} />
          <Badge value={summary.whatsapp_status} />
        </div>
      </div>

      <div>
        <span className="font-bold text-[10px] uppercase tracking-wider text-ink-400 block mb-2">
          Client Overview
        </span>
        <div className="space-y-1.5 text-xs">
          <div className="flex justify-between text-ink-600">
            <span>Client Type</span>
            <span className="font-medium text-ink-900">{humanize(c.client_type)}</span>
          </div>
          {c.pan && (
            <div className="flex justify-between text-ink-600">
              <span>PAN</span>
              <span className="font-mono font-medium text-ink-900">{c.pan}</span>
            </div>
          )}
          <div className="flex justify-between text-ink-600">
            <span>Outstanding</span>
            <span className="font-semibold text-rose-700">{summary.outstanding_amount}</span>
          </div>
        </div>
      </div>

      <div>
        <span className="font-bold text-[10px] uppercase tracking-wider text-ink-400 block mb-2">
          Active Tasks ({summary.counts.open_tasks ?? 0})
        </span>
        {!openTasks?.items.length ? (
          <p className="text-[11px] text-ink-400 italic">No open tasks</p>
        ) : (
          <ul className="space-y-1.5">
            {openTasks.items.map((t) => (
              <li key={t.id} className="rounded-lg bg-ink-50 p-2 space-y-0.5">
                <p className="font-semibold text-ink-900 truncate">{t.title}</p>
                <div className="flex justify-between text-[10px] text-ink-500">
                  <span>{t.service_type}</span>
                  <span>Due {fmtDate(t.due_date)}</span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div>
        <span className="font-bold text-[10px] uppercase tracking-wider text-ink-400 block mb-2">
          Recent Documents ({summary.counts.documents ?? 0})
        </span>
        {!recentDocs?.items.length ? (
          <p className="text-[11px] text-ink-400 italic">No files on record</p>
        ) : (
          <ul className="space-y-1.5">
            {recentDocs.items.map((d) => (
              <li key={d.id} className="rounded-lg bg-ink-50 p-2 space-y-0.5">
                <Link
                  to={`/documents/${d.id}`}
                  className="font-semibold text-ink-900 hover:text-brand-700 truncate block"
                >
                  {d.file_name}
                </Link>
                <div className="flex justify-between text-[10px] text-ink-500">
                  <span>v{d.version}</span>
                  <Badge value={d.status} />
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export function WhatsAppPage() {
  const [params, setParams] = useSearchParams();
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState("");
  const [sim, setSim] = useState(false);
  const dq = useDebounce(q);

  const account = useQuery({
    queryKey: ["wa-account"],
    queryFn: whatsappApi.account,
  });

  const { data, isLoading } = useQuery({
    queryKey: ["conversations", dq, filter],
    queryFn: () =>
      whatsappApi.conversations({
        q: dq,
        handover_state: filter === "HUMAN" ? "HUMAN" : undefined,
        unread_only: filter === "UNREAD",
      }),
    refetchInterval: 8000,
  });

  const selectedId = params.get("conversation") ?? data?.items[0]?.id;

  const selected = useQuery({
    queryKey: ["conversation", selectedId],
    queryFn: () => whatsappApi.conversation(selectedId!),
    enabled: !!selectedId,
    refetchInterval: 8000,
  });

  return (
    <div className="space-y-5">
      <PageHeader
        title="WhatsApp Inbox"
        subtitle={
          account.data && (
            <span className="flex items-center gap-2">
              Provider:{" "}
              <b className="text-ink-900">
                {account.data.provider === "meta"
                  ? "Meta WhatsApp Cloud API"
                  : "Mock Simulator (development)"}
              </b>
              · <Badge value={account.data.status} />
            </span>
          )
        }
        actions={
          account.data?.provider === "mock" && (
            <Button variant="secondary" onClick={() => setSim(true)} className="gap-1.5 shadow-sm">
              <FlaskConical className="h-4 w-4" />
              <span>Simulate client message</span>
            </Button>
          )
        }
      />

      <Card padded={false} className="border border-ink-200/80 shadow-card overflow-hidden">
        <div className="grid h-[calc(100vh-14rem)] min-h-[550px] grid-cols-1 md:grid-cols-[300px_1fr] xl:grid-cols-[300px_1fr_auto]">
          {/* Panel 1: Conversation List */}
          <div className="flex min-h-0 flex-col border-r border-ink-100/90 bg-white">
            <div className="space-y-2.5 border-b border-ink-100/90 p-3 bg-white">
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-ink-400" />
                <input
                  aria-label="Search conversations"
                  placeholder="Search contacts, messages…"
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                  className="h-8 w-full rounded-lg border border-ink-200 bg-ink-50/50 pl-8 pr-3 text-xs text-ink-900 placeholder:text-ink-400 focus:border-brand-600 focus:bg-white focus:outline-none focus:ring-1 focus:ring-brand-500 transition-all shadow-2xs"
                />
              </div>

              {/* Filter Tabs */}
              <div className="flex gap-1 text-xs">
                {[
                  ["", "All"],
                  ["HUMAN", "Needs a person"],
                  ["UNREAD", "Unread"],
                ].map(([v, l]) => (
                  <button
                    key={v}
                    type="button"
                    onClick={() => setFilter(v)}
                    className={cn(
                      "rounded-lg px-2.5 py-1 text-xs font-semibold transition-colors duration-100",
                      filter === v
                        ? "bg-brand-700 text-white shadow-2xs"
                        : "bg-ink-100/70 text-ink-600 hover:bg-ink-200/70"
                    )}
                  >
                    {l}
                  </button>
                ))}
              </div>
            </div>

            {/* Conversation Items List */}
            <ul className="flex-1 divide-y divide-ink-100/80 overflow-y-auto" aria-label="Conversations">
              {isLoading && <Spinner label="Loading threads…" />}
              {data?.items.length === 0 && <EmptyState title="No conversations found" />}
              {data?.items.map((c) => {
                const isSelected = c.id === selectedId;
                const contactName =
                  c.client?.name ?? c.contact.profile_name ?? `+${c.contact.wa_id}`;

                return (
                  <li key={c.id}>
                    <button
                      type="button"
                      onClick={() => setParams({ conversation: c.id })}
                      className={cn(
                        "w-full px-3.5 py-3 text-left transition-colors duration-100 flex items-start gap-3",
                        isSelected
                          ? "bg-brand-50/90 border-l-2 border-brand-700"
                          : "hover:bg-ink-50/70"
                      )}
                    >
                      <Avatar name={contactName} size="md" className="shrink-0 mt-0.5" />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center justify-between gap-1">
                          <span className="truncate text-xs font-semibold text-ink-950">
                            {contactName}
                          </span>
                          <span className="shrink-0 text-[10px] text-ink-400 tabular-nums font-medium">
                            {timeAgo(c.last_message_at)}
                          </span>
                        </div>
                        <p className="mt-0.5 truncate text-xs text-ink-500 font-normal">
                          {c.last_message_preview || "No message body"}
                        </p>
                        <div className="mt-1 flex items-center justify-between gap-1">
                          <div className="flex items-center gap-1">
                            {c.handover_state === "HUMAN_REQUESTED" && (
                              <Badge value="HUMAN_REQUESTED" label="Wants a person" />
                            )}
                          </div>
                          {c.unread_count > 0 && (
                            <span className="rounded-full bg-brand-600 px-1.5 py-0.2 text-[10px] font-bold text-white tabular-nums">
                              {c.unread_count}
                            </span>
                          )}
                        </div>
                      </div>
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>

          {/* Panel 2: Message Thread Canvas */}
          <div className="min-h-0 flex flex-col">
            {selected.data ? (
              <MessageThread conv={selected.data} />
            ) : (
              <EmptyState title="Select a conversation from the left to view messages" />
            )}
          </div>

          {/* Panel 3: Client Workspace Context Sidebar */}
          {selected.data?.client_id && (
            <ClientContextPanel clientId={selected.data.client_id} />
          )}
        </div>
      </Card>

      <Simulator open={sim} onClose={() => setSim(false)} />
    </div>
  );
}

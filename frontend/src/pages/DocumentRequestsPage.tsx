import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BellRing, CheckCircle2, Circle, FileText, FolderInput, Plus } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Badge, Button, Card, EmptyState, PageHeader, Pagination, ProgressBar, Select, Spinner } from "../components/ui";
import { RequestFormModal } from "../features/requests/RequestFormModal";
import { Can } from "../hooks/useAuth";
import { useToast } from "../hooks/useToast";
import { errorMessage } from "../services/api";
import { requestApi } from "../services/endpoints";
import { fmtDate, fmtDateTime } from "../utils/format";

export function DocumentRequestsPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [creating, setCreating] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["requests", status, page],
    queryFn: () => requestApi.list({ status, open_only: !status, page, page_size: 20 }),
  });

  const refresh = () => qc.invalidateQueries({ queryKey: ["requests"] });

  const mark = useMutation({
    mutationFn: (a: { id: string; item: string; received: boolean }) =>
      requestApi.markItem(a.id, a.item, a.received),
    onSuccess: refresh,
    onError: (e) => toast("error", errorMessage(e)),
  });

  const remind = useMutation({
    mutationFn: (id: string) => requestApi.remind(id),
    onSuccess: () => {
      refresh();
      toast("success", "Reminder queued on WhatsApp");
    },
    onError: (e) => toast("error", errorMessage(e)),
  });

  return (
    <div className="space-y-5">
      <PageHeader
        title="Document Requests"
        subtitle="Collect mandatory documents from clients seamlessly over WhatsApp and client portal."
        actions={
          <Can perm="DOCUMENT_REQUEST_CREATE">
            <Button onClick={() => setCreating(true)} className="gap-1.5 shadow-sm">
              <Plus className="h-4 w-4" />
              <span>Request documents</span>
            </Button>
          </Can>
        }
      />

      <div className="flex items-center gap-3">
        <Select
          aria-label="Status"
          className="w-56 text-xs h-9"
          placeholder="Open requests"
          options={["PENDING", "PARTIAL", "OVERDUE", "COMPLETE", "CANCELLED"]}
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setPage(1);
          }}
        />
        {status && (
          <Button size="xs" variant="ghost" onClick={() => setStatus("")}>
            Reset to open
          </Button>
        )}
      </div>

      {isLoading ? (
        <Spinner label="Loading document requests…" />
      ) : !data?.items.length ? (
        <Card className="border border-ink-200/80 shadow-card">
          <EmptyState
            icon={FolderInput}
            title="No document requests"
            hint="Create a request and ProDesk will send the checklist to the client on WhatsApp."
            action={
              <Can perm="DOCUMENT_REQUEST_CREATE">
                <Button size="sm" onClick={() => setCreating(true)}>
                  <Plus className="h-4 w-4" />
                  <span>Create first request</span>
                </Button>
              </Can>
            }
          />
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {data.items.map((r) => {
            const received = r.items.filter((i) => i.status === "RECEIVED").length;
            const total = Math.max(1, r.items.length);
            const isComplete = received === r.items.length;

            return (
              <Card
                key={r.id}
                title={
                  <div className="flex items-center gap-2 truncate">
                    <span className="truncate">{r.title}</span>
                    <span className="text-ink-400 font-normal">·</span>
                    <Link
                      to={`/clients/${r.client_id}`}
                      className="font-medium text-brand-700 hover:underline truncate"
                    >
                      {r.client.name}
                    </Link>
                  </div>
                }
                actions={<Badge value={r.status} />}
                className="border border-ink-200/80 shadow-card hover:shadow-card-hover transition-shadow"
              >
                {/* Progress metadata */}
                <div className="mb-2 flex items-center justify-between text-xs text-ink-500">
                  <span className="font-semibold text-ink-800 tabular-nums">
                    {received} of {r.items.length} items received
                  </span>
                  <span className="tabular-nums">Due {fmtDate(r.due_date)}</span>
                </div>

                <ProgressBar
                  value={received}
                  max={total}
                  color={isComplete ? "brand" : r.status === "OVERDUE" ? "rose" : "amber"}
                  className="mb-4"
                />

                {/* Instructions */}
                {r.instructions && (
                  <p className="mb-3 rounded-lg bg-ink-50/70 border border-ink-100 p-2.5 text-xs text-ink-700 leading-relaxed">
                    {r.instructions}
                  </p>
                )}

                {/* Item checklist */}
                <div className="space-y-1.5">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-ink-400 block mb-1">
                    Checklist items
                  </span>
                  {r.items.map((i) => (
                    <div
                      key={i.id}
                      className="flex items-center justify-between rounded-lg p-2 text-xs hover:bg-ink-50 transition-colors"
                    >
                      <button
                        type="button"
                        disabled={r.status === "CANCELLED"}
                        onClick={() =>
                          mark.mutate({ id: r.id, item: i.id, received: i.status !== "RECEIVED" })
                        }
                        aria-label={`Toggle ${i.name}`}
                        className="flex items-center gap-2.5 text-left disabled:cursor-default"
                      >
                        {i.status === "RECEIVED" ? (
                          <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
                        ) : (
                          <Circle className="h-4 w-4 text-ink-300 shrink-0" />
                        )}
                        <span
                          className={
                            i.status === "RECEIVED"
                              ? "text-ink-400 line-through font-normal"
                              : "text-ink-900 font-medium"
                          }
                        >
                          {i.name}
                        </span>
                      </button>

                      {i.document_id && (
                        <Link
                          to={`/documents/${i.document_id}`}
                          className="flex items-center gap-1 text-[11px] font-semibold text-brand-700 hover:text-brand-900 ml-2"
                        >
                          <FileText className="h-3 w-3" />
                          <span>View file</span>
                        </Link>
                      )}
                    </div>
                  ))}
                </div>

                {/* Reminders footer */}
                <div className="mt-4 flex items-center justify-between border-t border-ink-100/90 pt-3 text-[11px] text-ink-500">
                  <span>
                    {r.reminders_sent} reminder(s) sent
                    {r.last_reminder_at && ` · Last ${fmtDateTime(r.last_reminder_at)}`}
                  </span>

                  {["PENDING", "PARTIAL", "OVERDUE"].includes(r.status) && (
                    <Can perm="DOCUMENT_REQUEST_MANAGE">
                      <Button
                        size="xs"
                        variant="secondary"
                        loading={remind.isPending && remind.variables === r.id}
                        onClick={() => remind.mutate(r.id)}
                        className="gap-1.5"
                      >
                        <BellRing className="h-3.5 w-3.5" />
                        <span>Send reminder</span>
                      </Button>
                    </Can>
                  )}
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {data && <Pagination page={page} pageSize={20} total={data.total} onPage={setPage} />}
      <RequestFormModal open={creating} onClose={() => setCreating(false)} />
    </div>
  );
}

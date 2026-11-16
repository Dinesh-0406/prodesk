import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarClock, ExternalLink, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { Badge, Button, Card, EmptyState, ErrorBox, Input, Modal, PageHeader, Select, Spinner } from "../components/ui";
import { Can } from "../hooks/useAuth";
import { errorMessage } from "../services/api";
import { insightApi } from "../services/endpoints";
import { fmtDate, humanize } from "../utils/format";

const CATS = ["GST", "ITR", "TDS", "ADVANCE_TAX", "ROC", "AUDIT", "CUSTOM"];

export function CompliancePage() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [cat, setCat] = useState("");
  const [f, setF] = useState({
    category: "GST",
    title: "",
    due_date: "",
    period: "",
    source: "ADMIN_CONFIGURED",
    source_reference: "",
    reminder_days_before: 3,
  });

  const { data, isLoading } = useQuery({
    queryKey: ["compliance", cat],
    queryFn: () => insightApi.compliance({ category: cat }),
  });

  const create = useMutation({
    mutationFn: () =>
      insightApi.createCompliance({
        ...f,
        source_reference: f.source_reference || null,
        period: f.period || null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["compliance"] });
      setOpen(false);
      setF({
        category: "GST",
        title: "",
        due_date: "",
        period: "",
        source: "ADMIN_CONFIGURED",
        source_reference: "",
        reminder_days_before: 3,
      });
    },
  });

  const del = useMutation({
    mutationFn: (id: string) => insightApi.deleteCompliance(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["compliance"] }),
  });

  const byMonth = (data ?? []).reduce<Record<string, typeof data>>((acc, e) => {
    const k = new Date(`${e.due_date}T00:00:00`).toLocaleDateString("en-IN", {
      month: "long",
      year: "numeric",
    });
    (acc[k] ??= []).push(e);
    return acc;
  }, {});

  return (
    <div className="space-y-5">
      <PageHeader
        title="Compliance Calendar"
        subtitle="ProDesk never invents statutory deadlines. Every date here is entered by your firm or carries a verified source."
        actions={
          <Can perm="COMPLIANCE_MANAGE">
            <Button onClick={() => setOpen(true)} className="gap-1.5 shadow-sm">
              <Plus className="h-4 w-4" />
              <span>Add deadline</span>
            </Button>
          </Can>
        }
      />

      <div className="flex items-center gap-3">
        <Select
          aria-label="Category"
          className="w-48 text-xs h-9"
          placeholder="All statutory categories"
          options={CATS}
          value={cat}
          onChange={(e) => setCat(e.target.value)}
        />
        {cat && (
          <Button size="xs" variant="ghost" onClick={() => setCat("")}>
            Reset filter
          </Button>
        )}
      </div>

      {isLoading ? (
        <Spinner label="Loading compliance deadlines…" />
      ) : !data?.length ? (
        <Card className="border border-ink-200/80 shadow-card">
          <EmptyState
            icon={CalendarClock}
            title="No deadlines configured"
            hint="Add the due dates your firm tracks (verify against official notifications)."
            action={
              <Can perm="COMPLIANCE_MANAGE">
                <Button size="sm" onClick={() => setOpen(true)}>
                  <Plus className="h-4 w-4" />
                  <span>Add first deadline</span>
                </Button>
              </Can>
            }
          />
        </Card>
      ) : (
        <div className="space-y-5">
          {Object.entries(byMonth).map(([month, events]) => (
            <Card key={month} title={month} padded={false} className="border border-ink-200/80 shadow-card">
              <ul className="divide-y divide-ink-100/80">
                {events!.map((e) => {
                  const day = new Date(`${e.due_date}T00:00:00`).getDate();
                  const monthName = fmtDate(e.due_date).split(" ")[1];

                  return (
                    <li
                      key={e.id}
                      className="flex items-center justify-between gap-4 px-5 py-3 hover:bg-ink-50/50 transition-colors"
                    >
                      <div className="flex items-center gap-4 min-w-0">
                        {/* Calendar Day Block */}
                        <div className="flex h-12 w-12 flex-col items-center justify-center rounded-xl bg-ink-100/80 border border-ink-200/70 text-ink-950 shrink-0">
                          <span className="text-base font-bold leading-none tabular-nums">{day}</span>
                          <span className="text-[10px] uppercase font-bold text-ink-500 mt-0.5">
                            {monthName}
                          </span>
                        </div>

                        <div className="min-w-0">
                          <p className="font-semibold text-xs text-ink-950 truncate">{e.title}</p>
                          <div className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[11px] text-ink-500">
                            {e.period && <span className="font-medium text-ink-700">{e.period}</span>}
                            <span>·</span>
                            <span>{humanize(e.source)}</span>
                            {e.source_reference && (
                              <>
                                <span>·</span>
                                <a
                                  className="inline-flex items-center gap-1 font-semibold text-brand-700 hover:underline"
                                  href={e.source_reference}
                                  target="_blank"
                                  rel="noreferrer noopener"
                                >
                                  <span>Official source</span>
                                  <ExternalLink className="h-3 w-3" />
                                </a>
                              </>
                            )}
                            <span>·</span>
                            <span>{e.reminder_days_before}d reminder buffer</span>
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center gap-2.5 shrink-0">
                        <Badge value={e.category} color="blue" />
                        <Can perm="COMPLIANCE_MANAGE">
                          <Button
                            size="xs"
                            variant="ghost"
                            aria-label="Delete"
                            onClick={() => del.mutate(e.id)}
                            className="text-ink-400 hover:text-rose-600"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        </Can>
                      </div>
                    </li>
                  );
                })}
              </ul>
            </Card>
          ))}
        </div>
      )}

      {/* Add Compliance Deadline Modal */}
      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="Add Compliance Deadline"
        subtitle="Schedule verified statutory due date with client reminder lead time"
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button
              disabled={!f.title || !f.due_date}
              loading={create.isPending}
              onClick={() => create.mutate()}
              className="shadow-sm"
            >
              Save
            </Button>
          </>
        }
      >
        <div className="grid grid-cols-2 gap-3.5">
          {create.error && (
            <div className="col-span-2">
              <ErrorBox error={new Error(errorMessage(create.error))} />
            </div>
          )}
          <Select
            label="Category"
            options={CATS}
            value={f.category}
            onChange={(e) => setF({ ...f, category: e.target.value })}
          />
          <Input
            label="Due date"
            type="date"
            value={f.due_date}
            onChange={(e) => setF({ ...f, due_date: e.target.value })}
          />
          <div className="col-span-2">
            <Input
              label="Title"
              placeholder="e.g. GSTR-3B Monthly Return or ITR Filing for Non-Audit"
              value={f.title}
              onChange={(e) => setF({ ...f, title: e.target.value })}
            />
          </div>
          <Input
            label="Period"
            placeholder="e.g. Oct-2026 or Q2"
            value={f.period}
            onChange={(e) => setF({ ...f, period: e.target.value })}
          />
          <Input
            label="Remind days before"
            type="number"
            value={f.reminder_days_before}
            onChange={(e) => setF({ ...f, reminder_days_before: Number(e.target.value) })}
          />
          <Select
            label="Source"
            options={[
              { value: "ADMIN_CONFIGURED", label: "Configured by firm" },
              { value: "VERIFIED_SOURCE", label: "Verified official source" },
            ]}
            value={f.source}
            onChange={(e) => setF({ ...f, source: e.target.value })}
          />
          <Input
            label="Source reference (URL)"
            placeholder="https://incometax.gov.in/..."
            value={f.source_reference}
            onChange={(e) => setF({ ...f, source_reference: e.target.value })}
          />
        </div>
      </Modal>
    </div>
  );
}

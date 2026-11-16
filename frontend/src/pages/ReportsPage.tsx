import { useQuery } from "@tanstack/react-query";
import { BarChart3, Download } from "lucide-react";
import { useState } from "react";
import { Button, Card, EmptyState, PageHeader, Spinner } from "../components/ui";
import { insightApi } from "../services/endpoints";
import { cn, downloadBlob, humanize } from "../utils/format";

const LABELS: Record<string, string> = {
  "client-growth": "Client Growth",
  "pending-documents": "Pending Documents",
  "document-delivery": "Document Delivery",
  "task-completion": "Task Completion",
  "whatsapp-activity": "WhatsApp Activity",
  "invoice-collection": "Invoice Collection",
  "employee-workload": "Employee Workload",
  "overdue-tasks": "Overdue Tasks",
};

function MiniBars({ rows, keys }: { rows: Record<string, string | number>[]; keys: string[] }) {
  const max = Math.max(1, ...rows.flatMap((r) => keys.map((k) => Number(r[k]) || 0)));
  const colors = ["bg-brand-600", "bg-sky-500", "bg-amber-500", "bg-violet-500"];

  return (
    <div className="flex h-44 items-end gap-2 overflow-x-auto border-b border-ink-100 pb-3 pt-2">
      {rows.map((r, i) => (
        <div key={i} className="flex min-w-[34px] flex-1 flex-col items-center gap-1.5">
          <div className="flex h-36 w-full items-end justify-center gap-1">
            {keys.map((k, j) => {
              const val = Number(r[k]) || 0;
              const heightPct = Math.max(4, (val / max) * 100);
              return (
                <div
                  key={k}
                  title={`${humanize(k)}: ${r[k]}`}
                  className={cn("w-3 rounded-t-md transition-all duration-300 hover:brightness-110", colors[j % colors.length])}
                  style={{ height: `${heightPct}%` }}
                />
              );
            })}
          </div>
          <span className="whitespace-nowrap font-mono text-[10px] text-ink-500 font-medium">
            {String(Object.values(r)[0]).slice(-5)}
          </span>
        </div>
      ))}
    </div>
  );
}

export function ReportsPage() {
  const [name, setName] = useState("pending-documents");
  const { data: names = [] } = useQuery({
    queryKey: ["reports"],
    queryFn: insightApi.reports,
  });

  const { data, isLoading } = useQuery({
    queryKey: ["report", name],
    queryFn: () => insightApi.report(name),
  });

  const numericKeys = data
    ? data.columns.slice(1).filter((c) => data.rows.every((r) => !isNaN(Number(r[c]))))
    : [];

  const chartable =
    data &&
    [
      "client-growth",
      "document-delivery",
      "task-completion",
      "whatsapp-activity",
      "invoice-collection",
    ].includes(name) &&
    data.rows.length > 0;

  return (
    <div className="space-y-5">
      <PageHeader
        title="Practice Analytics & Reports"
        subtitle="Operational metrics, delivery logs and practice insights derived directly from your records."
        actions={
          <Button
            variant="secondary"
            onClick={async () =>
              downloadBlob(await insightApi.reportCsv(name), `prodesk-${name}.csv`)
            }
            className="gap-1.5 shadow-sm"
          >
            <Download className="h-4 w-4" />
            <span>Export CSV</span>
          </Button>
        }
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[240px_1fr]">
        {/* Reports Navigation Sidebar */}
        <div className="rounded-xl border border-ink-200/80 bg-white p-2 shadow-card space-y-1">
          <div className="px-3 py-2 text-[10px] font-bold uppercase tracking-wider text-ink-400">
            Available Reports
          </div>
          {names.map((n) => (
            <button
              key={n}
              onClick={() => setName(n)}
              className={cn(
                "flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-xs font-medium transition-colors",
                n === name
                  ? "bg-brand-50/90 text-brand-900 font-semibold"
                  : "text-ink-600 hover:bg-ink-50 hover:text-ink-950"
              )}
            >
              <span>{LABELS[n] ?? humanize(n)}</span>
              {n === name && <span className="h-1.5 w-1.5 rounded-full bg-brand-600" />}
            </button>
          ))}
        </div>

        {/* Report Content Card */}
        <Card title={LABELS[name] ?? humanize(name)} padded={false} className="border border-ink-200/80 shadow-card">
          {isLoading || !data ? (
            <Spinner label="Generating report data…" />
          ) : !data.rows.length ? (
            <EmptyState title="No records found for this report" icon={BarChart3} />
          ) : (
            <div className="divide-y divide-ink-100">
              {chartable && (
                <div className="p-6 bg-white space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold uppercase tracking-wider text-ink-500">
                      Trend Visualization
                    </span>
                    <div className="flex gap-4 text-xs">
                      {numericKeys.map((k, j) => (
                        <span key={k} className="flex items-center gap-1.5 text-xs text-ink-600 font-medium">
                          <span
                            className={cn(
                              "h-2.5 w-2.5 rounded-xs",
                              ["bg-brand-600", "bg-sky-500", "bg-amber-500", "bg-violet-500"][j % 4]
                            )}
                          />
                          <span>{humanize(k)}</span>
                        </span>
                      ))}
                    </div>
                  </div>
                  <MiniBars rows={data.rows} keys={numericKeys} />
                </div>
              )}

              <div className="overflow-x-auto">
                <table className="min-w-full text-xs">
                  <thead>
                    <tr className="border-b border-ink-100/90 bg-ink-50/50 text-left text-[11px] font-semibold uppercase tracking-wider text-ink-500">
                      {data.columns.map((c) => (
                        <th key={c} className="px-5 py-3 first:pl-6 last:pr-6">
                          {humanize(c)}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-ink-100/80 bg-white">
                    {data.rows.map((r, i) => (
                      <tr key={i} className="hover:bg-ink-50/40">
                        {data.columns.map((c) => (
                          <td key={c} className="px-5 py-3 tabular-nums text-ink-800 first:pl-6 last:pr-6">
                            {String(r[c] ?? "—")}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

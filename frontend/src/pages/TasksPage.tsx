import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Calendar, ListChecks, Plus, Search, UserCheck, X } from "lucide-react";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Badge, Button, Card, EmptyState, PageHeader, Pagination, Select, Spinner, Tabs } from "../components/ui";
import { TaskFormModal } from "../features/tasks/TaskFormModal";
import { Can, useAuth } from "../hooks/useAuth";
import { useDebounce } from "../hooks/useDebounce";
import { useToast } from "../hooks/useToast";
import { errorMessage } from "../services/api";
import { taskApi } from "../services/endpoints";
import { SERVICE_TYPES, TASK_STATUSES, fmtDate, humanize, isOverdue } from "../utils/format";

const BUCKETS = [
  ["open", "All open"],
  ["overdue", "Overdue"],
  ["today", "Today"],
  ["week", "This week"],
  ["mine", "Assigned to me"],
  ["completed", "Completed"],
] as const;

export function TasksPage() {
  const [params, setParams] = useSearchParams();
  const qc = useQueryClient();
  const toast = useToast();
  const { can } = useAuth();
  const bucket = params.get("bucket") ?? "open";
  const [q, setQ] = useState("");
  const [svc, setSvc] = useState("");
  const [page, setPage] = useState(1);
  const [creating, setCreating] = useState(false);
  const dq = useDebounce(q);

  const counts = useQuery({
    queryKey: ["tasks", "buckets"],
    queryFn: taskApi.buckets,
  });

  const { data, isLoading } = useQuery({
    queryKey: ["tasks", bucket, dq, svc, page, params.get("client")],
    queryFn: () =>
      taskApi.list({
        bucket,
        q: dq,
        service_type: svc,
        page,
        page_size: 25,
        client_id: params.get("client"),
        sort: bucket === "completed" ? "created_at" : "due_date",
        order: bucket === "completed" ? "desc" : "asc",
      }),
  });

  const update = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      taskApi.update(id, { status }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tasks"] });
      toast("success", "Task status updated");
    },
    onError: (e) => toast("error", errorMessage(e)),
  });

  const clearFilters = () => {
    setQ("");
    setSvc("");
    setPage(1);
  };

  return (
    <div className="space-y-5">
      <PageHeader
        title="Tasks & Filings"
        subtitle="Track deadlines, assign client engagements, and update statutory filing statuses."
        actions={
          <Can perm="TASK_CREATE">
            <Button onClick={() => setCreating(true)} className="gap-1.5 shadow-sm">
              <Plus className="h-4 w-4" />
              <span>New task</span>
            </Button>
          </Can>
        }
      />

      {/* Bucket Tabs */}
      <Tabs
        value={bucket}
        onChange={(v) => {
          setParams({ bucket: v });
          setPage(1);
        }}
        tabs={BUCKETS.map(([v, l]) => ({
          value: v,
          label: l,
          count: counts.data?.[v],
        }))}
      />

      <Card padded={false} className="border border-ink-200/80 shadow-card">
        {/* Filter Bar */}
        <div className="flex flex-wrap items-center gap-2.5 border-b border-ink-100/90 bg-ink-50/40 p-3.5">
          <div className="relative min-w-[16rem] flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-ink-400" />
            <input
              aria-label="Search tasks"
              placeholder="Search task or client…"
              value={q}
              onChange={(e) => {
                setQ(e.target.value);
                setPage(1);
              }}
              className="h-9 w-full rounded-lg border border-ink-200 bg-white pl-9 pr-8 text-xs text-ink-900 placeholder:text-ink-400 focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-500/15 transition-all shadow-2xs"
            />
            {q && (
              <button
                type="button"
                onClick={() => setQ("")}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 p-0.5 text-ink-400 hover:text-ink-700"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>

          <Select
            aria-label="Service"
            className="w-44 text-xs h-9"
            placeholder="All service types"
            options={SERVICE_TYPES}
            value={svc}
            onChange={(e) => {
              setSvc(e.target.value);
              setPage(1);
            }}
          />

          {(q || svc) && (
            <Button size="xs" variant="ghost" onClick={clearFilters} className="text-xs text-ink-500 hover:text-ink-800">
              Clear filters
            </Button>
          )}
        </div>

        {/* Task Items List */}
        {isLoading ? (
          <Spinner label="Loading tasks workspace…" />
        ) : !data?.items.length ? (
          <EmptyState
            icon={ListChecks}
            title={dq || svc ? "No tasks match filters" : "No tasks in this view"}
            hint={
              dq || svc
                ? "Try clearing search or filters."
                : "Create tasks to schedule ITR filings, audits, GST reconciliations and advisory jobs."
            }
            action={
              <Can perm="TASK_CREATE">
                <Button size="sm" onClick={() => setCreating(true)}>
                  <Plus className="h-4 w-4" />
                  <span>Create new task</span>
                </Button>
              </Can>
            }
          />
        ) : (
          <ul className="divide-y divide-ink-100/80">
            {data.items.map((t) => {
              const overdue = isOverdue(t.due_date) && !t.completed_at;

              return (
                <li
                  key={t.id}
                  className="grid grid-cols-12 items-center gap-3 px-5 py-3 hover:bg-ink-50/50 transition-colors text-xs"
                >
                  {/* Task Title & Client Context */}
                  <div className="col-span-12 md:col-span-5 min-w-0">
                    <p className="font-semibold text-xs text-ink-950 truncate">{t.title}</p>
                    <div className="mt-0.5 flex items-center gap-1.5 text-[11px] text-ink-500 truncate">
                      <Link
                        to={`/clients/${t.client_id}`}
                        className="font-medium text-brand-700 hover:underline truncate"
                      >
                        {t.client.name}
                      </Link>
                      <span>·</span>
                      <span className="font-medium text-ink-700">{t.service_type}</span>
                      {t.financial_year && (
                        <>
                          <span>·</span>
                          <span className="font-mono">FY {t.financial_year}</span>
                        </>
                      )}
                    </div>
                  </div>

                  {/* Assignee */}
                  <div className="col-span-4 md:col-span-2 text-ink-700">
                    {t.assigned_employee ? (
                      <span className="flex items-center gap-1 font-medium truncate">
                        <UserCheck className="h-3 w-3 text-brand-600 shrink-0" />
                        <span className="truncate">{t.assigned_employee.full_name}</span>
                      </span>
                    ) : (
                      <span className="text-ink-400 italic">Unassigned</span>
                    )}
                  </div>

                  {/* Due Date */}
                  <div className="col-span-4 md:col-span-2 tabular-nums">
                    <span
                      className={`inline-flex items-center gap-1 font-medium ${
                        overdue ? "text-rose-700 font-semibold" : "text-ink-600"
                      }`}
                    >
                      <Calendar className="h-3 w-3 shrink-0 opacity-70" />
                      <span>{fmtDate(t.due_date)}</span>
                    </span>
                    {overdue && (
                      <span className="block text-[10px] text-rose-600 font-medium">Overdue</span>
                    )}
                  </div>

                  {/* Priority */}
                  <div className="col-span-4 md:col-span-1">
                    <Badge value={t.priority} />
                  </div>

                  {/* Status Dropdown / Badge */}
                  <div className="col-span-12 md:col-span-2 flex justify-start md:justify-end">
                    {can("TASK_UPDATE") ? (
                      <Select
                        aria-label={`Status of ${t.title}`}
                        className="w-full text-xs h-8"
                        value={t.status}
                        options={TASK_STATUSES}
                        onChange={(e) => update.mutate({ id: t.id, status: e.target.value })}
                      />
                    ) : (
                      <Badge value={t.status} label={humanize(t.status)} />
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}

        {data && <Pagination page={page} pageSize={25} total={data.total} onPage={setPage} />}
      </Card>

      <TaskFormModal open={creating} onClose={() => setCreating(false)} />
    </div>
  );
}

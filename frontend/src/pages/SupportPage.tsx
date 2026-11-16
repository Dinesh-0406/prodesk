import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CalendarClock,
  Clock,
  Headphones,
  HelpCircle,
  MessageSquare,
  PhoneCall,
  User,
} from "lucide-react";
import { useMemo } from "react";
import { Link } from "react-router-dom";
import { Card, EmptyState, PageHeader, Select, Spinner } from "../components/ui";
import { insightApi } from "../services/endpoints";
import { fmtDateTime, humanize } from "../utils/format";

export function SupportPage() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["support"], queryFn: () => insightApi.support({ page_size: 50 }) });

  const upd = useMutation({
    mutationFn: (a: { id: string; status: string }) => insightApi.updateSupport(a.id, { status: a.status }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["support"] }),
  });

  const stats = useMemo(() => {
    const items = data?.items ?? [];
    return {
      open: items.filter((s) => s.status === "OPEN").length,
      inProgress: items.filter((s) => s.status === "IN_PROGRESS").length,
      resolved: items.filter((s) => s.status === "RESOLVED").length,
    };
  }, [data?.items]);

  const typeIcon = (type: string) => {
    switch (type) {
      case "CALLBACK":
        return <PhoneCall className="h-4 w-4 text-emerald-600" />;
      case "APPOINTMENT":
        return <CalendarClock className="h-4 w-4 text-brand-600" />;
      default:
        return <HelpCircle className="h-4 w-4 text-blue-600" />;
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Client requests"
        subtitle="Callbacks, appointments and questions raised by clients on WhatsApp or the portal."
      />

      {/* KPI Stats */}
      <div className="grid grid-cols-3 gap-3">
        <div className="flex items-center gap-3 rounded-xl border border-ink-200/80 bg-white p-3.5 shadow-card">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-50 text-amber-700">
            <Clock className="h-5 w-5" />
          </div>
          <div>
            <p className="text-xs font-medium uppercase tracking-wider text-ink-400">Open Requests</p>
            <p className="text-xl font-semibold tabular-nums text-ink-950">{stats.open}</p>
          </div>
        </div>

        <div className="flex items-center gap-3 rounded-xl border border-ink-200/80 bg-white p-3.5 shadow-card">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50 text-blue-700">
            <Headphones className="h-5 w-5" />
          </div>
          <div>
            <p className="text-xs font-medium uppercase tracking-wider text-ink-400">In Progress</p>
            <p className="text-xl font-semibold tabular-nums text-ink-950">{stats.inProgress}</p>
          </div>
        </div>

        <div className="flex items-center gap-3 rounded-xl border border-ink-200/80 bg-white p-3.5 shadow-card">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-50 text-emerald-700">
            <MessageSquare className="h-5 w-5" />
          </div>
          <div>
            <p className="text-xs font-medium uppercase tracking-wider text-ink-400">Resolved</p>
            <p className="text-xl font-semibold tabular-nums text-ink-950">{stats.resolved}</p>
          </div>
        </div>
      </div>

      <Card padded={false}>
        {isLoading ? (
          <div className="p-8">
            <Spinner />
          </div>
        ) : !data?.items.length ? (
          <EmptyState
            icon={<Headphones className="h-8 w-8" />}
            title="No client requests"
            description="Client callbacks and queries from WhatsApp and the portal will appear here."
          />
        ) : (
          <ul className="divide-y divide-ink-100">
            {data.items.map((s) => (
              <li
                key={s.id}
                className="flex flex-wrap items-center justify-between gap-4 p-4 transition-colors hover:bg-ink-50/40"
              >
                <div className="min-w-0 flex-1 space-y-1.5">
                  <div className="flex items-center gap-2">
                    <span className="flex items-center gap-1.5 rounded-full bg-ink-100 px-2.5 py-0.5 text-xs font-medium text-ink-800">
                      {typeIcon(s.request_type)}
                      {humanize(s.request_type)}
                    </span>
                    <span className="text-ink-300">·</span>
                    <Link
                      to={`/clients/${s.client_id}`}
                      className="flex items-center gap-1 text-sm font-semibold text-ink-950 hover:text-brand-700 hover:underline"
                    >
                      <User className="h-3.5 w-3.5 text-ink-400" />
                      {s.client.name}
                    </Link>
                  </div>
                  <p className="text-sm text-ink-700">{s.message}</p>
                  <p className="flex items-center gap-1 text-xs text-ink-400">
                    <Clock className="h-3 w-3" />
                    {fmtDateTime(s.created_at)}
                  </p>
                </div>

                <div className="w-40 shrink-0">
                  <Select
                    aria-label="Status"
                    value={s.status}
                    options={["OPEN", "IN_PROGRESS", "RESOLVED"]}
                    onChange={(e) => upd.mutate({ id: s.id, status: e.target.value })}
                  />
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

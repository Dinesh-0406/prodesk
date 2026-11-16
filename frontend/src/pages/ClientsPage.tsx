import { useQuery } from "@tanstack/react-query";
import { Plus, Search, Upload, UserCheck, Users, X } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Avatar, Badge, Button, Card, EmptyState, PageHeader, Pagination, Select, Spinner, Table } from "../components/ui";
import { ClientFormModal, ImportClientsModal } from "../features/clients/ClientForm";
import { Can } from "../hooks/useAuth";
import { useDebounce } from "../hooks/useDebounce";
import { clientApi, orgApi } from "../services/endpoints";
import type { Client } from "../types";
import { CLIENT_TYPES, fmtDate, humanize } from "../utils/format";

export function ClientsPage() {
  const nav = useNavigate();
  const [q, setQ] = useState("");
  const [type, setType] = useState("");
  const [status, setStatus] = useState("");
  const [assignee, setAssignee] = useState("");
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState("name");
  const [creating, setCreating] = useState(false);
  const [importing, setImporting] = useState(false);
  const dq = useDebounce(q);

  const { data: users = [] } = useQuery({
    queryKey: ["users"],
    queryFn: orgApi.users,
  });

  const { data, isLoading } = useQuery({
    queryKey: ["clients", dq, type, status, assignee, page, sort],
    queryFn: () =>
      clientApi.list({
        q: dq,
        client_type: type,
        status,
        assigned_employee_id: assignee,
        page,
        page_size: 25,
        sort,
        order: sort === "name" ? "asc" : "desc",
      }),
  });

  const clearFilters = () => {
    setQ("");
    setType("");
    setStatus("");
    setAssignee("");
    setSort("name");
    setPage(1);
  };

  const hasActiveFilters = Boolean(q || type || status || assignee || sort !== "name");

  return (
    <div className="space-y-5">
      <PageHeader
        title="Clients"
        subtitle={
          data
            ? `Manage relationships, compliance documents and communication for ${data.total} clients.`
            : "Manage relationships, documents and automated client communications."
        }
        actions={
          <Can perm="CLIENT_CREATE">
            <Button variant="secondary" onClick={() => setImporting(true)} className="gap-1.5">
              <Upload className="h-4 w-4" />
              <span>Import CSV</span>
            </Button>
            <Button onClick={() => setCreating(true)} className="gap-1.5 shadow-sm">
              <Plus className="h-4 w-4" />
              <span>New client</span>
            </Button>
          </Can>
        }
      />

      <Card padded={false} className="border border-ink-200/80 shadow-card">
        {/* Filter Bar */}
        <div className="flex flex-wrap items-center gap-2.5 border-b border-ink-100/90 bg-ink-50/40 p-3.5">
          <div className="relative min-w-[16rem] flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-ink-400" />
            <input
              aria-label="Search clients"
              placeholder="Search name, phone, PAN, GSTIN, email…"
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
            aria-label="Client type"
            className="w-40 text-xs h-9"
            placeholder="All client types"
            options={CLIENT_TYPES}
            value={type}
            onChange={(e) => {
              setType(e.target.value);
              setPage(1);
            }}
          />

          <Select
            aria-label="Status"
            className="w-36 text-xs h-9"
            placeholder="All statuses"
            options={["ACTIVE", "INACTIVE", "ARCHIVED"]}
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setPage(1);
            }}
          />

          <Select
            aria-label="Assigned employee"
            className="w-44 text-xs h-9"
            placeholder="All staff members"
            options={users.map((u) => ({ value: u.id, label: u.full_name }))}
            value={assignee}
            onChange={(e) => {
              setAssignee(e.target.value);
              setPage(1);
            }}
          />

          <Select
            aria-label="Sort"
            className="w-40 text-xs h-9"
            options={[
              { value: "name", label: "Name (A–Z)" },
              { value: "created_at", label: "Newest first" },
              { value: "updated_at", label: "Recently updated" },
            ]}
            value={sort}
            onChange={(e) => setSort(e.target.value)}
          />

          {hasActiveFilters && (
            <Button size="xs" variant="ghost" onClick={clearFilters} className="text-xs text-ink-500 hover:text-ink-800">
              Clear filters
            </Button>
          )}
        </div>

        {/* Data Table */}
        {isLoading ? (
          <Spinner label="Loading clients directory…" />
        ) : (
          <Table<Client>
            rows={data?.items ?? []}
            onRowClick={(c) => nav(`/clients/${c.id}`)}
            empty={
              <EmptyState
                icon={Users}
                title={dq ? "No clients match your search" : "No clients in your directory"}
                hint={
                  dq
                    ? "Try adjusting your search criteria or clear applied filters."
                    : "Add your first client to start organizing documents, tasks and WhatsApp updates."
                }
                action={
                  <Can perm="CLIENT_CREATE">
                    <Button size="sm" onClick={() => setCreating(true)}>
                      <Plus className="h-4 w-4" />
                      <span>Add new client</span>
                    </Button>
                  </Can>
                }
              />
            }
            columns={[
              {
                key: "name",
                header: "Client Profile",
                render: (c) => (
                  <div className="flex items-center gap-3">
                    <Avatar name={c.name} size="sm" />
                    <div className="min-w-0">
                      <p className="font-semibold text-xs text-ink-950 hover:text-brand-700 transition-colors">
                        {c.name}
                      </p>
                      <p className="text-[11px] text-ink-500 font-mono">{c.phone}</p>
                    </div>
                  </div>
                ),
              },
              {
                key: "type",
                header: "Type",
                render: (c) => (
                  <span className="text-xs font-medium text-ink-700">{humanize(c.client_type)}</span>
                ),
              },
              {
                key: "pan",
                header: "PAN & GSTIN",
                render: (c) => (
                  <div className="font-mono text-[11px] space-y-0.5">
                    <p className={c.pan ? "text-ink-800 font-medium" : "text-ink-400"}>
                      {c.pan ?? "—"}
                    </p>
                    {c.gstin && <p className="text-[10px] text-ink-500">{c.gstin}</p>}
                  </div>
                ),
              },
              {
                key: "emp",
                header: "Assigned To",
                render: (c) =>
                  c.assigned_employee ? (
                    <div className="flex items-center gap-1.5 text-xs text-ink-800">
                      <UserCheck className="h-3.5 w-3.5 text-brand-600" />
                      <span>{c.assigned_employee.full_name}</span>
                    </div>
                  ) : (
                    <span className="text-xs text-ink-400 italic">Unassigned</span>
                  ),
              },
              {
                key: "wa",
                header: "WhatsApp Consent",
                render: (c) => (
                  <Badge
                    value={
                      c.whatsapp_opt_out_at
                        ? "OPTED_OUT"
                        : c.whatsapp_opt_in
                        ? "OPTED_IN"
                        : "NOT_OPTED_IN"
                    }
                  />
                ),
              },
              {
                key: "status",
                header: "Status",
                render: (c) => <Badge value={c.status} />,
              },
              {
                key: "created",
                header: "Added",
                render: (c) => <span className="text-xs text-ink-500 tabular-nums">{fmtDate(c.created_at)}</span>,
              },
            ]}
          />
        )}

        {data && <Pagination page={page} pageSize={25} total={data.total} onPage={setPage} />}
      </Card>

      <ClientFormModal
        open={creating}
        onClose={() => setCreating(false)}
        onSaved={(c) => nav(`/clients/${c.id}`)}
      />
      <ImportClientsModal open={importing} onClose={() => setImporting(false)} />
    </div>
  );
}

import { useQuery } from "@tanstack/react-query";
import { FileText, Plus, Search, Upload, X } from "lucide-react";
import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Badge, Button, Card, EmptyState, PageHeader, Pagination, Select, Spinner, Table } from "../components/ui";
import { UploadDocumentModal } from "../features/documents/UploadDocumentModal";
import { Can } from "../hooks/useAuth";
import { useDebounce } from "../hooks/useDebounce";
import { documentApi } from "../services/endpoints";
import type { Doc } from "../types";
import { DOCUMENT_TYPES, financialYears, fileSize, fmtDate, humanize } from "../utils/format";

export function DocumentsPage() {
  const nav = useNavigate();
  const [params, setParams] = useSearchParams();
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [uploading, setUploading] = useState(false);
  const dq = useDebounce(q);

  const filter = (k: string) => params.get(k) ?? "";
  const setFilter = (k: string, v: string) => {
    const p = new URLSearchParams(params);
    if (v) p.set(k, v);
    else p.delete(k);
    setParams(p);
    setPage(1);
  };

  const { data, isLoading } = useQuery({
    queryKey: ["documents", dq, filter("status"), filter("type"), filter("fy"), filter("source"), page],
    queryFn: () =>
      documentApi.list({
        q: dq,
        status: filter("status"),
        document_type: filter("type"),
        financial_year: filter("fy"),
        source: filter("source"),
        page,
        page_size: 25,
      }),
  });

  const clearFilters = () => {
    setQ("");
    setParams(new URLSearchParams());
    setPage(1);
  };

  const hasActiveFilters = Boolean(
    q || filter("status") || filter("type") || filter("fy") || filter("source")
  );

  return (
    <div className="space-y-5">
      <PageHeader
        title="Document Vault"
        subtitle="Every file is private, SHA256 checksummed, versioned and access-logged."
        actions={
          <Can perm="DOCUMENT_UPLOAD">
            <Button onClick={() => setUploading(true)} className="gap-1.5 shadow-sm">
              <Upload className="h-4 w-4" />
              <span>Upload document</span>
            </Button>
          </Can>
        }
      />

      <Card padded={false} className="border border-ink-200/80 shadow-card">
        {/* Filter Bar */}
        <div className="flex flex-wrap items-center gap-2.5 border-b border-ink-100/90 bg-ink-50/40 p-3.5">
          <div className="relative min-w-[14rem] flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-ink-400" />
            <input
              aria-label="Search documents"
              placeholder="Search file name or description…"
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
            aria-label="Status"
            className="w-40 text-xs h-9"
            placeholder="All statuses"
            options={["UPLOADED", "UNDER_REVIEW", "APPROVED", "REJECTED", "DELIVERED", "ARCHIVED"]}
            value={filter("status")}
            onChange={(e) => setFilter("status", e.target.value)}
          />

          <Select
            aria-label="Document type"
            className="w-48 text-xs h-9"
            placeholder="All document types"
            options={DOCUMENT_TYPES}
            value={filter("type")}
            onChange={(e) => setFilter("type", e.target.value)}
          />

          <Select
            aria-label="Financial year"
            className="w-32 text-xs h-9"
            placeholder="All FY"
            options={financialYears(8)}
            value={filter("fy")}
            onChange={(e) => setFilter("fy", e.target.value)}
          />

          <Select
            aria-label="Source"
            className="w-44 text-xs h-9"
            placeholder="All sources"
            options={[
              { value: "STAFF", label: "Prepared by firm" },
              { value: "CLIENT_PORTAL", label: "Client portal" },
              { value: "WHATSAPP", label: "WhatsApp" },
            ]}
            value={filter("source")}
            onChange={(e) => setFilter("source", e.target.value)}
          />

          {hasActiveFilters && (
            <Button size="xs" variant="ghost" onClick={clearFilters} className="text-xs text-ink-500 hover:text-ink-800">
              Clear filters
            </Button>
          )}
        </div>

        {/* Data Table */}
        {isLoading ? (
          <Spinner label="Loading documents vault…" />
        ) : (
          <Table<Doc>
            rows={data?.items ?? []}
            onRowClick={(d) => nav(`/documents/${d.id}`)}
            empty={
              <EmptyState
                icon={FileText}
                title={dq || hasActiveFilters ? "No documents match filters" : "Document vault is empty"}
                hint={
                  dq || hasActiveFilters
                    ? "Try adjusting search or status filters."
                    : "Upload prepared ITRs, GST returns or compliance records to deliver to clients."
                }
                action={
                  <Can perm="DOCUMENT_UPLOAD">
                    <Button size="sm" onClick={() => setUploading(true)}>
                      <Plus className="h-4 w-4" />
                      <span>Upload first document</span>
                    </Button>
                  </Can>
                }
              />
            }
            columns={[
              {
                key: "f",
                header: "Document File",
                render: (d) => (
                  <div className="flex items-center gap-3">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-ink-100 text-ink-600 border border-ink-200/60 shrink-0">
                      <FileText className="h-4 w-4" />
                    </div>
                    <div className="min-w-0">
                      <p className="font-semibold text-xs text-ink-950 hover:text-brand-700 transition-colors truncate">
                        {d.file_name}
                      </p>
                      <p className="text-[11px] text-ink-500">
                        {fileSize(d.file_size)} · v{d.version}
                      </p>
                    </div>
                  </div>
                ),
              },
              {
                key: "c",
                header: "Client",
                render: (d) => (
                  <span className="text-xs font-semibold text-ink-900 hover:underline">{d.client.name}</span>
                ),
              },
              {
                key: "t",
                header: "Type",
                render: (d) => <span className="text-xs text-ink-700">{humanize(d.document_type)}</span>,
              },
              {
                key: "fy",
                header: "FY",
                render: (d) => <span className="text-xs text-ink-600 font-mono">{d.financial_year ?? "—"}</span>,
              },
              {
                key: "src",
                header: "Source",
                render: (d) => (
                  <span className="text-xs text-ink-600 bg-ink-100/70 px-2 py-0.5 rounded text-[11px]">
                    {humanize(d.source)}
                  </span>
                ),
              },
              {
                key: "s",
                header: "Status",
                render: (d) => <Badge value={d.status} />,
              },
              {
                key: "u",
                header: "Last Updated",
                render: (d) => <span className="text-xs text-ink-500 tabular-nums">{fmtDate(d.updated_at)}</span>,
              },
            ]}
          />
        )}

        {data && <Pagination page={page} pageSize={25} total={data.total} onPage={setPage} />}
      </Card>

      <UploadDocumentModal
        open={uploading}
        onClose={() => setUploading(false)}
        onUploaded={(d) => nav(`/documents/${d.id}`)}
      />
    </div>
  );
}

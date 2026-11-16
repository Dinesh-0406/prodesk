import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Archive,
  ArrowLeft,
  CheckCircle2,
  Download,
  Eye,
  FileCheck2,
  Send,
  Sparkles,
  Upload,
  XCircle,
} from "lucide-react";
import { useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ACCEPT } from "../components/FileDrop";
import { Badge, Button, Card, EmptyState, KeyValue, Modal, Spinner, Textarea } from "../components/ui";
import { Can } from "../hooks/useAuth";
import { useToast } from "../hooks/useToast";
import { errorMessage } from "../services/api";
import { documentApi } from "../services/endpoints";
import type { DocDetail } from "../types";
import { fileSize, fmtDate, fmtDateTime, humanize } from "../utils/format";

function suggestion(d: DocDetail): { document_type?: string | null; financial_year?: string | null } | null {
  const v = d.extracted_metadata?.[`v${d.version}`] as
    | { suggestion?: { document_type?: string | null; financial_year?: string | null } }
    | undefined;
  return v?.suggestion ?? null;
}

export function DocumentDetailPage() {
  const { id = "" } = useParams();
  const nav = useNavigate();
  const qc = useQueryClient();
  const toast = useToast();
  const fileRef = useRef<HTMLInputElement>(null);
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");

  const { data: d, isLoading } = useQuery({
    queryKey: ["document", id],
    queryFn: () => documentApi.get(id),
  });

  const done = (msg: string) => () => {
    qc.invalidateQueries({ queryKey: ["document", id] });
    qc.invalidateQueries({ queryKey: ["documents"] });
    toast("success", msg);
  };
  const fail = (e: unknown) => toast("error", errorMessage(e));

  const approve = useMutation({
    mutationFn: (deliver: boolean) => documentApi.approve(id, { deliver }),
    onSuccess: (_, deliver) =>
      done(deliver ? "Approved — WhatsApp notification queued" : "Approved")(),
    onError: fail,
  });

  const reject = useMutation({
    mutationFn: () => documentApi.reject(id, reason),
    onSuccess: () => {
      setRejecting(false);
      done("Document rejected")();
    },
    onError: fail,
  });

  const submit = useMutation({
    mutationFn: () => documentApi.submit(id),
    onSuccess: done("Submitted for review"),
    onError: fail,
  });

  const deliver = useMutation({
    mutationFn: () => documentApi.deliver(id),
    onSuccess: done("Delivery sent on WhatsApp"),
    onError: fail,
  });

  const archive = useMutation({
    mutationFn: () => documentApi.archive(id),
    onSuccess: done("Archived"),
    onError: fail,
  });

  const version = useMutation({
    mutationFn: (f: File) => documentApi.newVersion(id, f),
    onSuccess: done("New version uploaded — needs approval"),
    onError: fail,
  });

  const open = async (inline: boolean, version_id?: string) => {
    try {
      const r = await documentApi.downloadUrl(id, { inline, version_id });
      window.open(r.url, "_blank", "noopener,noreferrer");
    } catch (e) {
      fail(e);
    }
  };

  if (isLoading || !d) {
    return <Spinner label="Loading document details…" />;
  }

  const s = suggestion(d);
  const reviewable = d.status === "UPLOADED" || d.status === "UNDER_REVIEW";
  const staffDoc = d.source === "STAFF";

  return (
    <div className="space-y-6">
      {/* ----------------------------- HEADER ----------------------------- */}
      <div className="rounded-2xl border border-ink-200/80 bg-white p-6 shadow-card">
        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div className="min-w-0 space-y-1.5">
            <div className="flex items-center gap-2 text-xs text-ink-500 font-medium">
              <button
                type="button"
                onClick={() => nav("/documents")}
                className="flex items-center gap-1 hover:text-ink-800 transition-colors"
              >
                <ArrowLeft className="h-3.5 w-3.5" />
                <span>Documents</span>
              </button>
              <span>/</span>
              <Link to={`/clients/${d.client_id}`} className="text-brand-700 hover:underline">
                {d.client.name}
              </Link>
            </div>

            <div className="flex flex-wrap items-center gap-2.5">
              <h1 className="text-2xl font-bold tracking-tight text-ink-950 truncate">{d.file_name}</h1>
              <Badge value={d.status} />
              <span className="font-mono text-xs bg-ink-100/80 px-2 py-0.5 rounded text-ink-700 font-semibold">
                v{d.version}
              </span>
            </div>

            <p className="text-xs text-ink-500">
              {humanize(d.document_type)} {d.financial_year && `· FY ${d.financial_year}`}{" "}
              · {fileSize(d.file_size)} · Uploaded {fmtDateTime(d.created_at)}
            </p>
          </div>

          {/* Header Action Toolbar */}
          <div className="flex flex-wrap items-center gap-2 pt-1">
            {["application/pdf", "image/png", "image/jpeg"].includes(d.mime_type) && (
              <Button variant="secondary" size="sm" onClick={() => open(true)} className="gap-1.5">
                <Eye className="h-3.5 w-3.5" />
                <span>Preview</span>
              </Button>
            )}
            <Can perm="DOCUMENT_DOWNLOAD">
              <Button variant="secondary" size="sm" onClick={() => open(false)} className="gap-1.5">
                <Download className="h-3.5 w-3.5" />
                <span>Download</span>
              </Button>
            </Can>
            <Can perm="DOCUMENT_UPLOAD">
              <Button
                variant="secondary"
                size="sm"
                loading={version.isPending}
                onClick={() => fileRef.current?.click()}
                className="gap-1.5"
              >
                <Upload className="h-3.5 w-3.5" />
                <span>New version</span>
              </Button>
              <input
                ref={fileRef}
                type="file"
                accept={ACCEPT}
                className="hidden"
                aria-label="New version file"
                onChange={(e) => e.target.files?.[0] && version.mutate(e.target.files[0])}
              />
            </Can>
          </div>
        </div>
      </div>

      {/* ----------------------------- MAIN 2-COLUMN WORKSPACE ----------------------------- */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Left Column: Review, Delivery, Versions, Delivery Log */}
        <div className="space-y-6 lg:col-span-2">
          {/* Review & Approval Action Card */}
          {reviewable && staffDoc && (
            <div className="rounded-xl border border-brand-200/80 bg-brand-50/40 p-5 shadow-card">
              <div className="flex items-center gap-2.5 mb-2">
                <FileCheck2 className="h-5 w-5 text-brand-700" />
                <h2 className="text-sm font-bold text-brand-950">Review & Approval Sign-off</h2>
              </div>
              <p className="text-xs text-brand-900 leading-relaxed font-normal">
                Approving this record makes version {d.version} available to {d.client.name}. With auto-delivery enabled, they receive an instant WhatsApp notification with a one-time-password protected download link.
              </p>
              <div className="mt-4 flex flex-wrap items-center gap-2.5">
                {d.status === "UPLOADED" && (
                  <Button
                    size="sm"
                    variant="secondary"
                    loading={submit.isPending}
                    onClick={() => submit.mutate()}
                  >
                    Submit for review
                  </Button>
                )}
                <Can perm="DOCUMENT_APPROVE">
                  <Button
                    size="sm"
                    loading={approve.isPending && approve.variables === true}
                    onClick={() => approve.mutate(true)}
                    className="gap-1.5 shadow-sm"
                  >
                    <CheckCircle2 className="h-4 w-4" />
                    <span>Approve & send on WhatsApp</span>
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    loading={approve.isPending && approve.variables === false}
                    onClick={() => approve.mutate(false)}
                  >
                    Approve only
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => setRejecting(true)}
                    className="text-rose-700 hover:bg-rose-50"
                  >
                    <XCircle className="h-4 w-4" />
                    <span>Reject</span>
                  </Button>
                </Can>
              </div>
            </div>
          )}

          {/* Delivery Dispatch Card */}
          {(d.status === "APPROVED" || d.status === "DELIVERED") && staffDoc && (
            <Card title="WhatsApp Delivery Dispatch">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                <p className="text-xs text-ink-600">
                  Send current approved version (v{d.version}) to {d.client.name} via verified WhatsApp template.
                </p>
                <Can perm="DOCUMENT_SHARE">
                  <Button
                    size="sm"
                    loading={deliver.isPending}
                    onClick={() => deliver.mutate()}
                    className="gap-1.5 shrink-0"
                  >
                    <Send className="h-3.5 w-3.5" />
                    <span>{d.status === "DELIVERED" ? "Resend on WhatsApp" : "Send on WhatsApp"}</span>
                  </Button>
                </Can>
              </div>
            </Card>
          )}

          {/* Versions History */}
          <Card title="File Versions" subtitle="Immutable versions with SHA256 checksums" padded={false}>
            <ul className="divide-y divide-ink-100/80">
              {[...d.versions].reverse().map((v) => (
                <li
                  key={v.id}
                  className="flex items-center justify-between gap-3 px-5 py-3 hover:bg-ink-50/50 text-xs"
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-xs text-ink-950 font-mono">v{v.version_number}</span>
                      <span className="font-medium text-ink-800 truncate">{v.file_name}</span>
                    </div>
                    <p className="text-[11px] text-ink-500 mt-0.5">
                      {fileSize(v.file_size)} · Uploaded {fmtDateTime(v.created_at)}
                      {v.review_note && ` · “${v.review_note}”`}
                    </p>
                    <p className="font-mono text-[10px] text-ink-400 mt-0.5">
                      SHA256: {v.checksum_sha256.slice(0, 24)}…
                    </p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <Badge value={v.status} />
                    <Can perm="DOCUMENT_DOWNLOAD">
                      <Button
                        size="xs"
                        variant="ghost"
                        aria-label={`Download v${v.version_number}`}
                        onClick={() => open(false, v.id)}
                      >
                        <Download className="h-3.5 w-3.5" />
                      </Button>
                    </Can>
                  </div>
                </li>
              ))}
            </ul>
          </Card>

          {/* WhatsApp Deliveries Audit Table */}
          <Card title="Delivery History" subtitle="WhatsApp notification and client download tracking" padded={false}>
            {d.deliveries.length === 0 ? (
              <EmptyState title="No deliveries sent yet" hint="Delivery events will appear once sent over WhatsApp." />
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full text-xs">
                  <thead>
                    <tr className="border-b border-ink-100/90 bg-ink-50/50 text-left text-[11px] font-semibold uppercase tracking-wider text-ink-500">
                      <th className="px-5 py-2.5">Status</th>
                      <th className="px-4 py-2.5">Sent</th>
                      <th className="px-4 py-2.5">Delivered</th>
                      <th className="px-4 py-2.5">Read</th>
                      <th className="px-4 py-2.5">Downloaded</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-ink-100/80">
                    {d.deliveries.map((x) => (
                      <tr key={x.id} className="hover:bg-ink-50/50">
                        <td className="px-5 py-2.5">
                          <Badge value={x.status} />
                          {x.error && <p className="mt-1 text-rose-600 font-medium">{x.error}</p>}
                        </td>
                        <td className="px-4 py-2.5 tabular-nums text-ink-600">{fmtDateTime(x.sent_at)}</td>
                        <td className="px-4 py-2.5 tabular-nums text-ink-600">{fmtDateTime(x.delivered_at)}</td>
                        <td className="px-4 py-2.5 tabular-nums text-ink-600">{fmtDateTime(x.read_at)}</td>
                        <td className="px-4 py-2.5 tabular-nums text-ink-600">
                          {fmtDateTime(x.downloaded_at)}
                          {x.download_count > 1 && (
                            <span className="ml-1 text-brand-700 font-semibold">({x.download_count}×)</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>

        {/* Right Column: Metadata Details & Access History */}
        <div className="space-y-6">
          <Card title="Document Metadata">
            <KeyValue
              items={[
                ["Document Type", humanize(d.document_type)],
                ["Financial Year", d.financial_year],
                ["Assessment Year", d.assessment_year],
                ["Source", humanize(d.source)],
                ["File Size", fileSize(d.file_size)],
                ["Uploaded Date", fmtDate(d.created_at)],
              ]}
            />

            {d.description && (
              <div className="mt-4 rounded-lg bg-ink-50/70 border border-ink-100 p-3 text-xs text-ink-700">
                <p className="font-semibold text-ink-900 mb-1">Description</p>
                <p>{d.description}</p>
              </div>
            )}

            {/* AI Document Intelligence Suggestion */}
            {s?.document_type && s.document_type !== d.document_type && (
              <div className="mt-4 rounded-xl border border-violet-200/80 bg-violet-50/60 p-3.5 text-xs text-violet-900">
                <div className="flex items-center gap-1.5 font-bold text-violet-950 mb-1">
                  <Sparkles className="h-3.5 w-3.5 text-violet-600" />
                  <span>AI Document Intelligence</span>
                </div>
                <p>
                  Suggested classification: <b>{humanize(s.document_type)}</b>
                  {s.financial_year && ` (FY ${s.financial_year})`}.
                </p>
              </div>
            )}

            <Can perm="DOCUMENT_UPLOAD">
              {d.status !== "ARCHIVED" && (
                <Button
                  size="sm"
                  variant="outline"
                  className="mt-4 w-full justify-center gap-1.5 text-ink-600"
                  onClick={() => archive.mutate()}
                >
                  <Archive className="h-3.5 w-3.5" />
                  <span>Archive document</span>
                </Button>
              )}
            </Can>
          </Card>

          {/* Access Audit Trail */}
          <Card title="Access Log" subtitle="Every download, preview and export is tracked" padded={false}>
            <ul className="max-h-80 divide-y divide-ink-100/80 overflow-y-auto">
              {d.access_history.length === 0 ? (
                <li className="px-5 py-6 text-center text-xs text-ink-500">No access events recorded.</li>
              ) : (
                d.access_history.map((a, i) => (
                  <li key={i} className="px-5 py-2.5 text-xs hover:bg-ink-50/50">
                    <p className="font-semibold text-ink-900">{humanize(a.action)}</p>
                    <p className="text-[11px] text-ink-500 mt-0.5">
                      {humanize(a.actor_type)} · {fmtDateTime(a.timestamp)}
                      {a.ip && ` · IP: ${a.ip}`}
                    </p>
                  </li>
                ))
              )}
            </ul>
          </Card>
        </div>
      </div>

      {/* Reject Reason Modal */}
      <Modal
        open={rejecting}
        onClose={() => setRejecting(false)}
        title="Reject Document"
        subtitle="Explain what needs correction before staff can resubmit"
        footer={
          <>
            <Button variant="secondary" onClick={() => setRejecting(false)}>
              Cancel
            </Button>
            <Button
              variant="danger"
              disabled={!reason.trim()}
              loading={reject.isPending}
              onClick={() => reject.mutate()}
            >
              Reject Document
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          <Textarea
            label="Rejection reason / review note"
            placeholder="e.g. Signature missing on page 3, please re-upload signed version."
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
        </div>
      </Modal>
    </div>
  );
}

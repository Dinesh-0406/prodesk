import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Building2,
  Calendar,
  CheckCircle2,
  Circle,
  Clock,
  CreditCard,
  Download,
  FileCheck,
  FileSpreadsheet,
  FileText,
  Headphones,
  MessageSquare,
  Send,
  ShieldCheck,
  Upload,
  User,
} from "lucide-react";
import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorBox,
  Field,
  KeyValue,
  Modal,
  Select,
  Spinner,
  StatCard,
  Table,
  Textarea,
} from "../../components/ui";
import { ACCEPT } from "../../components/FileDrop";
import { useToast } from "../../hooks/useToast";
import { errorMessage } from "../../services/api";
import { portalApi } from "../../services/endpoints";
import type { Doc, Invoice, Payment } from "../../types";
import { fmtDate, fmtDateTime, humanize, money } from "../../utils/format";

export function PortalDashboard() {
  const { data } = useQuery({ queryKey: ["portal", "dashboard"], queryFn: portalApi.dashboard });
  if (!data) return <Spinner />;

  return (
    <div className="space-y-6">
      {/* Welcome Banner */}
      <div className="rounded-2xl border border-ink-200/80 bg-gradient-to-r from-brand-900 via-brand-800 to-teal-900 p-6 text-white shadow-card">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <span className="inline-flex items-center gap-1.5 rounded-full bg-white/10 px-3 py-1 text-xs font-medium text-emerald-200 backdrop-blur-xs">
              <ShieldCheck className="h-3.5 w-3.5" />
              Secure Client Workspace
            </span>
            <h2 className="mt-2 text-xl font-bold tracking-tight sm:text-2xl">Client Overview</h2>
            <p className="mt-1 text-xs text-brand-100 sm:text-sm">
              Track your tax filings, share requested documents, and review invoices in real time.
            </p>
          </div>
          <Link
            to="/portal/requests"
            className="inline-flex items-center gap-2 rounded-xl bg-white px-4 py-2.5 text-xs font-semibold text-brand-900 shadow-sm hover:bg-brand-50 transition-colors"
          >
            <Upload className="h-4 w-4 text-brand-700" />
            Upload documents
          </Link>
        </div>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label="My documents" value={data.documents} />
        <StatCard
          label="Documents requested"
          value={data.pending_requests}
          tone={data.pending_requests ? "warn" : "default"}
        />
        <StatCard label="Open invoices" value={data.open_invoices} />
        <StatCard
          label="Amount due"
          value={money(data.outstanding)}
          tone={Number(data.outstanding) > 0 ? "warn" : "good"}
        />
      </div>

      {/* Actionable Sections Grid */}
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <Card
          title={
            <span className="flex items-center gap-2">
              <FileCheck className="h-4 w-4 text-brand-700" />
              Your CA needs
            </span>
          }
          actions={
            <Link to="/portal/requests" className="text-xs font-medium text-brand-700 hover:underline">
              Upload
            </Link>
          }
        >
          {!data.requests.length ? (
            <div className="flex items-center gap-2.5 py-3 text-xs text-ink-500">
              <CheckCircle2 className="h-4 w-4 text-emerald-600" />
              <span>Nothing pending at this time. Thank you!</span>
            </div>
          ) : (
            <div className="space-y-3">
              {data.requests.map((r) => (
                <div key={r.id} className="rounded-xl border border-ink-200/80 bg-ink-50/50 p-3.5">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-semibold text-ink-950">{r.title}</p>
                    <span className="text-xs text-ink-500">due {fmtDate(r.due_date)}</span>
                  </div>
                  <p className="mt-1 text-xs text-ink-600">
                    <span className="font-medium text-ink-700">Required:</span>{" "}
                    {r.items
                      .filter((i) => i.status === "PENDING")
                      .map((i) => i.name)
                      .join(", ")}
                  </p>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card
          title={
            <span className="flex items-center gap-2">
              <FileSpreadsheet className="h-4 w-4 text-brand-700" />
              Work in progress
            </span>
          }
        >
          {!data.tasks.length ? (
            <p className="py-3 text-xs text-ink-500">No active work orders right now.</p>
          ) : (
            <div className="divide-y divide-ink-100">
              {data.tasks.map((t, i) => (
                <div key={i} className="flex items-center justify-between py-2.5 text-sm">
                  <span className="font-medium text-ink-900">{t.title}</span>
                  <Badge value={t.status} />
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

export function PortalDocuments() {
  const toast = useToast();
  const { data, isLoading } = useQuery({
    queryKey: ["portal", "documents"],
    queryFn: () => portalApi.documents({ page_size: 100 }),
  });

  const open = async (d: Doc) => {
    try {
      const r = await portalApi.documentUrl(d.id);
      window.location.assign(r.url);
    } catch (e) {
      toast("error", errorMessage(e));
    }
  };

  return (
    <div className="space-y-6">
      <Card
        title={
          <span className="flex items-center gap-2">
            <FileText className="h-4 w-4 text-brand-700" />
            My Documents
          </span>
        }
        description="Official acknowledgements, tax returns, computation sheets, and audit filings shared with you."
        padded={false}
      >
        {isLoading ? (
          <div className="p-8">
            <Spinner />
          </div>
        ) : (
          <Table<Doc>
            rows={data?.items ?? []}
            empty={<EmptyState title="No documents shared yet" description="Documents shared by your CA will appear here." />}
            columns={[
              {
                key: "f",
                header: "Document",
                render: (d) => (
                  <div className="flex items-center gap-2.5 py-1">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-50 text-brand-700">
                      <FileText className="h-4 w-4" />
                    </div>
                    <div>
                      <span className="font-medium text-ink-950">{d.file_name}</span>
                      <p className="text-[11px] text-ink-400">{fmtDateTime(d.created_at)}</p>
                    </div>
                  </div>
                ),
              },
              {
                key: "t",
                header: "Type",
                render: (d) => (
                  <span className="rounded bg-ink-100 px-2 py-0.5 text-xs font-medium text-ink-800">
                    {humanize(d.document_type)}
                  </span>
                ),
              },
              { key: "fy", header: "FY", render: (d) => <span className="font-mono text-xs">{d.financial_year ?? "—"}</span> },
              {
                key: "s",
                header: "",
                render: (d) => (
                  <Badge
                    value={d.source === "STAFF" ? "DELIVERED" : "UPLOADED"}
                    label={d.source === "STAFF" ? "From your CA" : "Uploaded by you"}
                  />
                ),
              },
              {
                key: "a",
                header: "",
                render: (d) => (
                  <div className="flex justify-end">
                    <Button size="sm" variant="secondary" onClick={() => open(d)}>
                      <Download className="h-3.5 w-3.5" />
                      Download
                    </Button>
                  </div>
                ),
              },
            ]}
          />
        )}
      </Card>
    </div>
  );
}

export function PortalRequests() {
  const qc = useQueryClient();
  const toast = useToast();
  const input = useRef<HTMLInputElement>(null);
  const [target, setTarget] = useState<{ req: string; item: string } | null>(null);

  const { data, isLoading } = useQuery({ queryKey: ["portal", "requests"], queryFn: portalApi.requests });

  const up = useMutation({
    mutationFn: (f: File) => portalApi.upload(target!.req, f, target!.item),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["portal"] });
      toast("success", "Document uploaded successfully — thank you!");
    },
    onError: (e) => toast("error", errorMessage(e)),
  });

  if (isLoading) return <Spinner />;

  return (
    <div className="space-y-6">
      <input
        ref={input}
        type="file"
        accept={ACCEPT}
        className="hidden"
        aria-label="Upload file"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) up.mutate(f);
          e.target.value = "";
        }}
      />

      {/* Header Explainer */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-ink-950">Document Requests</h2>
          <p className="mt-0.5 text-xs text-ink-500">
            Please submit the required records below for compliance and filing.
          </p>
        </div>
      </div>

      {!data?.items.length ? (
        <Card>
          <EmptyState
            icon={<CheckCircle2 className="h-8 w-8 text-emerald-600" />}
            title="No document requests"
            description="All requested records have been received or your CA has not opened any requests yet."
          />
        </Card>
      ) : (
        <div className="space-y-4">
          {data?.items.map((r) => (
            <Card
              key={r.id}
              title={r.title}
              actions={<Badge value={r.status} />}
              description={r.instructions}
            >
              <div className="space-y-3 pt-1">
                <div className="flex items-center gap-1.5 text-xs font-medium text-ink-500">
                  <Calendar className="h-3.5 w-3.5 text-ink-400" />
                  Due {fmtDate(r.due_date)}
                </div>

                <ul className="divide-y divide-ink-100 rounded-xl border border-ink-200/80 bg-ink-50/40">
                  {r.items.map((i) => (
                    <li key={i.id} className="flex items-center justify-between p-3">
                      <span className="flex items-center gap-2.5 text-sm font-medium text-ink-900">
                        {i.status === "RECEIVED" ? (
                          <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                        ) : (
                          <Circle className="h-4 w-4 text-ink-300" />
                        )}
                        {i.name}
                      </span>
                      {i.status === "PENDING" && r.status !== "CANCELLED" && (
                        <Button
                          size="sm"
                          variant="secondary"
                          loading={up.isPending && target?.item === i.id}
                          onClick={() => {
                            setTarget({ req: r.id, item: i.id });
                            input.current?.click();
                          }}
                        >
                          <Upload className="h-3.5 w-3.5" />
                          Upload
                        </Button>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Tip Banner */}
      <div className="rounded-xl border border-brand-200/60 bg-brand-50/40 p-3.5 text-xs text-brand-900 flex items-center gap-2.5">
        <MessageSquare className="h-4 w-4 shrink-0 text-brand-600" />
        <span>
          Tip: You can also attach and send documents directly in your WhatsApp conversation with the firm.
        </span>
      </div>
    </div>
  );
}

export function PortalTasks() {
  const { data, isLoading } = useQuery({ queryKey: ["portal", "tasks"], queryFn: portalApi.tasks });
  if (isLoading) return <Spinner />;

  return (
    <div className="space-y-6">
      <Card
        title={
          <span className="flex items-center gap-2">
            <FileSpreadsheet className="h-4 w-4 text-brand-700" />
            Work Status
          </span>
        }
        description="Real-time progress on tax returns, audit statements, and compliance filings."
        padded={false}
      >
        {!data?.length ? (
          <EmptyState title="No work on record" description="No active work orders are recorded for your profile." />
        ) : (
          <ul className="divide-y divide-ink-100">
            {data.map((t) => (
              <li
                key={t.id}
                className="flex flex-wrap items-center justify-between gap-4 p-4 transition-colors hover:bg-ink-50/40"
              >
                <div>
                  <p className="font-semibold text-ink-950">{t.title}</p>
                  <p className="mt-0.5 text-xs text-ink-500">
                    {t.service_type}
                    {t.financial_year && ` · FY ${t.financial_year}`}
                    {t.filed_at && ` · filed ${fmtDate(t.filed_at)}`}
                  </p>
                </div>
                <Badge value={t.status} label={t.status_label} />
              </li>
            ))}
          </ul>
        )}
        <div className="border-t border-ink-100 bg-ink-50/40 px-4 py-2.5 text-[11px] text-ink-400">
          Status as recorded by your CA's office.
        </div>
      </Card>
    </div>
  );
}

declare global {
  interface Window {
    Razorpay?: new (o: Record<string, unknown>) => { open: () => void };
  }
}

function loadRazorpay(): Promise<void> {
  return new Promise((res, rej) => {
    if (window.Razorpay) return res();
    const s = document.createElement("script");
    s.src = "https://checkout.razorpay.com/v1/checkout.js";
    s.onload = () => res();
    s.onerror = () => rej(new Error("Could not load Razorpay checkout"));
    document.body.appendChild(s);
  });
}

export function PortalInvoices() {
  const qc = useQueryClient();
  const toast = useToast();
  const [mock, setMock] = useState<{ order_id: string; amount: number; number: string } | null>(null);
  const { data, isLoading } = useQuery({ queryKey: ["portal", "invoices"], queryFn: portalApi.invoices });

  const paid = () => {
    qc.invalidateQueries({ queryKey: ["portal"] });
    toast("success", "Payment verified — thank you!");
  };

  const verify = useMutation({
    mutationFn: portalApi.verifyPayment,
    onSuccess: paid,
    onError: (e) => toast("error", errorMessage(e)),
  });

  const pay = useMutation({
    mutationFn: (inv: Invoice) => portalApi.checkout(inv.id),
    onSuccess: async (co) => {
      if (co.provider === "mock") {
        setMock({ order_id: co.order_id, amount: co.amount_paise, number: co.invoice_number });
        return;
      }
      await loadRazorpay();
      new window.Razorpay!({
        key: co.key_id,
        order_id: co.order_id,
        amount: co.amount_paise,
        currency: co.currency,
        name: co.firm_name,
        description: `Invoice ${co.invoice_number}`,
        handler: (r: { razorpay_order_id: string; razorpay_payment_id: string; razorpay_signature: string }) =>
          verify.mutate(r),
      }).open();
    },
    onError: (e) => toast("error", errorMessage(e)),
  });

  const mockPay = useMutation({
    mutationFn: async (succeed: boolean) => {
      const sig = await portalApi.mockComplete(mock!.order_id, succeed);
      return succeed ? portalApi.verifyPayment(sig) : null;
    },
    onSuccess: (r) => {
      setMock(null);
      if (r) paid();
      else toast("error", "Payment failed (simulated)");
    },
    onError: (e) => toast("error", errorMessage(e)),
  });

  return (
    <div className="space-y-6">
      <Card
        title={
          <span className="flex items-center gap-2">
            <CreditCard className="h-4 w-4 text-brand-700" />
            Invoices
          </span>
        }
        description="Review billing statements and settle dues securely with UPI, Net Banking, or Cards."
        padded={false}
      >
        {isLoading ? (
          <div className="p-8">
            <Spinner />
          </div>
        ) : (
          <Table<Invoice>
            rows={data?.items ?? []}
            empty={<EmptyState title="No invoices" description="All accounts are settled. No invoices found." />}
            columns={[
              {
                key: "n",
                header: "Invoice",
                render: (i) => <span className="font-mono font-medium text-ink-950">{i.invoice_number}</span>,
              },
              { key: "d", header: "Due", render: (i) => <span className="text-xs">{fmtDate(i.due_date)}</span> },
              {
                key: "t",
                header: "Total",
                render: (i) => <span className="font-mono text-xs tabular-nums">{money(i.total)}</span>,
              },
              {
                key: "b",
                header: "Balance",
                render: (i) => (
                  <span className="font-mono text-xs font-semibold tabular-nums text-rose-700">
                    {money(i.balance_due)}
                  </span>
                ),
              },
              { key: "s", header: "Status", render: (i) => <Badge value={i.status} /> },
              {
                key: "p",
                header: "",
                render: (i) =>
                  ["SENT", "OVERDUE", "PARTIALLY_PAID"].includes(i.status) && (
                    <div className="flex justify-end">
                      <Button
                        size="sm"
                        loading={pay.isPending && pay.variables?.id === i.id}
                        onClick={() => pay.mutate(i)}
                      >
                        <CreditCard className="h-3.5 w-3.5" />
                        Pay {money(i.balance_due)}
                      </Button>
                    </div>
                  ),
              },
            ]}
          />
        )}
      </Card>

      <Modal
        open={!!mock}
        onClose={() => setMock(null)}
        title="Mock payment gateway (development)"
        description="This stands in for Razorpay Checkout. The server still verifies the payment signature and status before marking invoice paid."
        footer={
          <>
            <Button variant="secondary" onClick={() => mockPay.mutate(false)}>
              Simulate failure
            </Button>
            <Button loading={mockPay.isPending} onClick={() => mockPay.mutate(true)}>
              Pay {money((mock?.amount ?? 0) / 100)}
            </Button>
          </>
        }
      >
        <p className="text-sm text-ink-600">
          Simulate paying invoice <strong className="text-ink-950">{mock?.number}</strong>.
        </p>
      </Modal>
    </div>
  );
}

export function PortalPayments() {
  const { data, isLoading } = useQuery({ queryKey: ["portal", "payments"], queryFn: portalApi.payments });

  return (
    <div className="space-y-6">
      <Card
        title={
          <span className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-emerald-600" />
            Payment History
          </span>
        }
        description="Receipts and verification timestamps for all settled transactions."
        padded={false}
      >
        {isLoading ? (
          <div className="p-8">
            <Spinner />
          </div>
        ) : (
          <Table<Payment>
            rows={data?.items ?? []}
            empty={<EmptyState title="No payments yet" description="Your payment receipts will appear here." />}
            columns={[
              {
                key: "a",
                header: "Amount",
                render: (p) => <span className="font-mono text-xs font-semibold tabular-nums">{money(p.amount)}</span>,
              },
              { key: "m", header: "Method", render: (p) => <span className="text-xs">{humanize(p.method ?? p.provider)}</span> },
              {
                key: "d",
                header: "Paid on",
                render: (p) => <span className="text-xs text-ink-500">{fmtDateTime(p.paid_at)}</span>,
              },
              {
                key: "s",
                header: "",
                render: (p) => <Badge value={p.status === "CAPTURED" ? "PAID" : p.status} />,
              },
            ]}
          />
        )}
      </Card>
    </div>
  );
}

export function PortalMessages() {
  const { data, isLoading } = useQuery({ queryKey: ["portal", "messages"], queryFn: portalApi.messages });

  return (
    <div className="space-y-6">
      <Card
        title={
          <span className="flex items-center gap-2">
            <MessageSquare className="h-4 w-4 text-emerald-600" />
            WhatsApp messages with your CA
          </span>
        }
        description="Chronological log of verified communication sent between your WhatsApp number and the firm."
      >
        {isLoading ? (
          <div className="py-8">
            <Spinner />
          </div>
        ) : !data?.length ? (
          <EmptyState title="No messages yet" description="Messages exchanged with the firm will appear here." />
        ) : (
          <div className="space-y-3 pt-2">
            {data.map((m, i) => (
              <div key={i} className={`flex flex-col ${m.direction === "INBOUND" ? "items-end" : "items-start"}`}>
                <div
                  className={`max-w-[85%] whitespace-pre-wrap rounded-2xl px-4 py-2.5 text-sm shadow-xs ${
                    m.direction === "INBOUND"
                      ? "rounded-br-xs bg-brand-700 text-white"
                      : "rounded-bl-xs bg-ink-100 text-ink-900 border border-ink-200/80"
                  }`}
                >
                  {m.body}
                </div>
                <p className="mt-1 px-1 text-[10px] text-ink-400">{fmtDateTime(m.timestamp)}</p>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}

export function PortalSupport() {
  const qc = useQueryClient();
  const toast = useToast();
  const [type, setType] = useState("QUERY");
  const [msg, setMsg] = useState("");
  const { data } = useQuery({ queryKey: ["portal", "support"], queryFn: portalApi.support });

  const m = useMutation({
    mutationFn: () => portalApi.createSupport(type, msg),
    onSuccess: () => {
      setMsg("");
      qc.invalidateQueries({ queryKey: ["portal", "support"] });
      toast("success", "Request sent to your CA");
    },
    onError: (e) => toast("error", errorMessage(e)),
  });

  return (
    <div className="space-y-6">
      <Card
        title={
          <span className="flex items-center gap-2">
            <Headphones className="h-4 w-4 text-brand-700" />
            Contact your CA
          </span>
        }
        description="Raise a direct query, book an appointment, or request a phone callback."
      >
        <div className="space-y-4">
          {m.error && <ErrorBox error={new Error(errorMessage(m.error))} />}

          <Field label="Request type">
            <Select
              value={type}
              onChange={(e) => setType(e.target.value)}
              options={[
                { value: "QUERY", label: "Question" },
                { value: "CALLBACK", label: "Request a call back" },
                { value: "APPOINTMENT", label: "Book an appointment" },
              ]}
            />
          </Field>

          <Textarea
            label="Message"
            placeholder="Describe your question or preferred appointment time..."
            value={msg}
            onChange={(e) => setMsg(e.target.value)}
          />

          <div className="flex justify-end pt-1">
            <Button disabled={msg.length < 2} loading={m.isPending} onClick={() => m.mutate()}>
              <Send className="h-4 w-4" />
              Send
            </Button>
          </div>
        </div>
      </Card>

      <Card
        title={
          <span className="flex items-center gap-2">
            <Clock className="h-4 w-4 text-brand-700" />
            My requests
          </span>
        }
        padded={false}
      >
        {!data?.items.length ? (
          <div className="p-6 text-center text-xs text-ink-500">No requests submitted yet.</div>
        ) : (
          <ul className="divide-y divide-ink-100">
            {data?.items.map((s) => (
              <li key={s.id} className="flex items-center justify-between p-4 text-sm">
                <div>
                  <span className="font-semibold text-ink-900">{humanize(s.request_type)}</span>
                  <span className="text-ink-400"> · </span>
                  <span className="text-ink-700">{s.message}</span>
                </div>
                <Badge value={s.status} />
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

export function PortalProfile() {
  const { data } = useQuery({ queryKey: ["portal", "me"], queryFn: portalApi.me });
  if (!data) return <Spinner />;

  return (
    <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
      <Card
        title={
          <span className="flex items-center gap-2">
            <User className="h-4 w-4 text-brand-700" />
            My Profile
          </span>
        }
      >
        <KeyValue
          items={[
            ["Name", data.name],
            ["Mobile", data.phone],
            ["Email", data.email as string],
            ["Type", humanize(data.client_type as string)],
            ["PAN", data.pan as string],
            ["GSTIN", data.gstin as string],
            ["Address", data.address as string],
            ["WhatsApp updates", data.whatsapp_opt_in ? "Subscribed" : "Not subscribed"],
          ]}
        />
        <div className="mt-4 rounded-lg bg-ink-50/60 p-3 text-xs text-ink-500">
          To update your contact details or business credentials, please message your CA. Reply <b>STOP</b> on
          WhatsApp anytime to unsubscribe from notifications.
        </div>
      </Card>

      <Card
        title={
          <span className="flex items-center gap-2">
            <Building2 className="h-4 w-4 text-brand-700" />
            Your CA firm
          </span>
        }
      >
        <KeyValue
          items={[
            ["Firm", data.organization.name],
            ["Phone", data.organization.phone],
            ["Email", data.organization.email],
            ["Address", data.organization.address],
          ]}
        />
      </Card>
    </div>
  );
}

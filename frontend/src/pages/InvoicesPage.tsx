import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CreditCard, Plus, Send } from "lucide-react";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Badge, Button, Card, EmptyState, Input, Modal, PageHeader, Pagination, Select, Spinner, Table, Tabs } from "../components/ui";
import { InvoiceFormModal } from "../features/invoices/InvoiceFormModal";
import { Can } from "../hooks/useAuth";
import { useToast } from "../hooks/useToast";
import { errorMessage } from "../services/api";
import { billingApi } from "../services/endpoints";
import type { Invoice, Payment } from "../types";
import { fmtDate, fmtDateTime, humanize, money } from "../utils/format";

function InvoiceDrawer({ id, onClose }: { id: string; onClose: () => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [pay, setPay] = useState({ amount: "", reference: "", method: "BANK_TRANSFER" });

  const { data: inv } = useQuery({
    queryKey: ["invoice", id],
    queryFn: () => billingApi.invoice(id),
  });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["invoice", id] });
    qc.invalidateQueries({ queryKey: ["invoices"] });
    qc.invalidateQueries({ queryKey: ["payments"] });
  };

  const send = useMutation({
    mutationFn: () => billingApi.send(id),
    onSuccess: () => {
      refresh();
      toast("success", "Invoice dispatched to client on WhatsApp");
    },
    onError: (e) => toast("error", errorMessage(e)),
  });

  const cancel = useMutation({
    mutationFn: () => billingApi.cancel(id),
    onSuccess: () => {
      refresh();
      toast("success", "Invoice marked cancelled");
    },
    onError: (e) => toast("error", errorMessage(e)),
  });

  const record = useMutation({
    mutationFn: () => billingApi.recordPayment(id, pay),
    onSuccess: () => {
      refresh();
      toast("success", "Offline payment recorded successfully");
      setPay({ amount: "", reference: "", method: "BANK_TRANSFER" });
    },
    onError: (e) => toast("error", errorMessage(e)),
  });

  return (
    <Modal
      open
      onClose={onClose}
      title={inv ? `Invoice ${inv.invoice_number}` : "Invoice Details"}
      subtitle={inv ? `Issued to ${inv.client.name}` : undefined}
      wide
    >
      {!inv ? (
        <Spinner label="Loading invoice details…" />
      ) : (
        <div className="space-y-5">
          {/* Header Card */}
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-ink-100 bg-ink-50/50 p-4">
            <div>
              <Link
                to={`/clients/${inv.client_id}`}
                className="font-bold text-sm text-brand-700 hover:underline"
              >
                {inv.client.name}
              </Link>
              <p className="text-xs text-ink-500 mt-0.5">
                Issued {fmtDate(inv.issue_date)} · Due {fmtDate(inv.due_date)}
                {inv.sent_at && ` · Sent ${fmtDateTime(inv.sent_at)}`}
              </p>
            </div>
            <Badge value={inv.status} />
          </div>

          {/* Line Items Table */}
          <div className="rounded-xl border border-ink-200/90 overflow-hidden shadow-2xs">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-ink-100 bg-ink-50/70 text-left font-semibold uppercase tracking-wider text-ink-500">
                  <th className="px-4 py-2.5">Item Description</th>
                  <th className="px-3 py-2.5">Qty</th>
                  <th className="px-3 py-2.5">Rate</th>
                  <th className="px-3 py-2.5">GST</th>
                  <th className="px-4 py-2.5 text-right">Amount</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-ink-100/80 bg-white">
                {inv.items.map((i) => (
                  <tr key={i.id} className="hover:bg-ink-50/40">
                    <td className="px-4 py-2.5">
                      <p className="font-semibold text-ink-950">{i.description}</p>
                      {i.sac_code && (
                        <p className="font-mono text-[10px] text-ink-400">SAC: {i.sac_code}</p>
                      )}
                    </td>
                    <td className="px-3 py-2.5 tabular-nums text-ink-600">{Number(i.quantity)}</td>
                    <td className="px-3 py-2.5 tabular-nums text-ink-600">{money(i.unit_price)}</td>
                    <td className="px-3 py-2.5 tabular-nums text-ink-600">{Number(i.tax_rate)}%</td>
                    <td className="px-4 py-2.5 text-right font-medium tabular-nums text-ink-900">
                      {money(Number(i.amount) + Number(i.tax_amount))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Totals Breakdown */}
          <div className="ml-auto w-72 rounded-xl border border-ink-200/90 bg-ink-50/50 p-4 space-y-2 text-xs">
            <div className="flex justify-between text-ink-500">
              <span>Subtotal</span>
              <span className="tabular-nums font-medium text-ink-900">{money(inv.subtotal)}</span>
            </div>
            <div className="flex justify-between text-ink-500">
              <span>GST Total</span>
              <span className="tabular-nums font-medium text-ink-900">{money(inv.tax)}</span>
            </div>
            <div className="flex justify-between border-t border-ink-200/80 pt-1.5 font-bold text-ink-950">
              <span>Total Invoice Amount</span>
              <span className="tabular-nums text-sm text-brand-900">{money(inv.total)}</span>
            </div>
            <div className="flex justify-between text-emerald-700 font-semibold">
              <span>Amount Paid</span>
              <span className="tabular-nums">{money(inv.amount_paid)}</span>
            </div>
            <div className="flex justify-between border-t border-ink-200/80 pt-1.5 font-bold text-rose-700">
              <span>Balance Due</span>
              <span className="tabular-nums text-sm">{money(inv.balance_due)}</span>
            </div>
          </div>

          {/* Invoice Actions */}
          <Can perm="INVOICE_CREATE">
            <div className="flex flex-wrap items-center gap-2.5 border-t border-ink-100 pt-4">
              {["DRAFT", "SENT", "OVERDUE", "PARTIALLY_PAID"].includes(inv.status) && (
                <Button
                  loading={send.isPending}
                  onClick={() => send.mutate()}
                  className="gap-1.5 shadow-sm"
                >
                  <Send className="h-4 w-4" />
                  <span>{inv.status === "DRAFT" ? "Send to client on WhatsApp" : "Resend on WhatsApp"}</span>
                </Button>
              )}
              {Number(inv.amount_paid) === 0 && inv.status !== "CANCELLED" && (
                <Button variant="ghost" onClick={() => cancel.mutate()} className="text-rose-600 hover:bg-rose-50">
                  Cancel invoice
                </Button>
              )}
            </div>

            {/* Offline Payment Recording Form */}
            {["SENT", "OVERDUE", "PARTIALLY_PAID"].includes(inv.status) && (
              <div className="rounded-xl border border-ink-200/90 bg-white p-4 shadow-2xs space-y-3">
                <p className="text-xs font-bold text-ink-950">Record Offline Payment</p>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
                  <Input
                    aria-label="Amount"
                    placeholder="Amount (₹)"
                    type="number"
                    value={pay.amount}
                    onChange={(e) => setPay({ ...pay, amount: e.target.value })}
                  />
                  <Input
                    aria-label="Reference"
                    placeholder="UTR / Cheque no."
                    value={pay.reference}
                    onChange={(e) => setPay({ ...pay, reference: e.target.value })}
                  />
                  <Select
                    aria-label="Method"
                    options={["BANK_TRANSFER", "UPI", "CHEQUE", "CASH"]}
                    value={pay.method}
                    onChange={(e) => setPay({ ...pay, method: e.target.value })}
                  />
                </div>
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={!pay.amount || pay.reference.length < 2}
                  loading={record.isPending}
                  onClick={() => record.mutate()}
                  className="gap-1.5"
                >
                  <CreditCard className="h-3.5 w-3.5" />
                  <span>Record payment</span>
                </Button>
              </div>
            )}
          </Can>
        </div>
      )}
    </Modal>
  );
}

export function InvoicesPage() {
  const [params, setParams] = useSearchParams();
  const [tab, setTab] = useState("invoices");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [creating, setCreating] = useState(false);
  const openId = params.get("open");

  const invoices = useQuery({
    queryKey: ["invoices", status, page],
    queryFn: () => billingApi.invoices({ status, page, page_size: 25 }),
    enabled: tab === "invoices",
  });

  const payments = useQuery({
    queryKey: ["payments", page],
    queryFn: () => billingApi.payments({ page, page_size: 25 }),
    enabled: tab === "payments",
  });

  return (
    <div className="space-y-5">
      <PageHeader
        title="Invoices & Payments"
        subtitle="Manage practice billings, track client payments, and send instant WhatsApp payment links."
        actions={
          <Can perm="INVOICE_CREATE">
            <Button onClick={() => setCreating(true)} className="gap-1.5 shadow-sm">
              <Plus className="h-4 w-4" />
              <span>New invoice</span>
            </Button>
          </Can>
        }
      />

      <Tabs
        value={tab}
        onChange={(v) => {
          setTab(v);
          setPage(1);
        }}
        tabs={[
          { value: "invoices", label: "Invoices" },
          { value: "payments", label: "Payments" },
        ]}
      />

      <Card padded={false} className="border border-ink-200/80 shadow-card">
        {tab === "invoices" && (
          <>
            <div className="border-b border-ink-100/90 bg-ink-50/40 p-3.5">
              <Select
                aria-label="Status"
                className="w-48 text-xs h-9"
                placeholder="All invoice statuses"
                options={["DRAFT", "SENT", "PARTIALLY_PAID", "PAID", "OVERDUE", "CANCELLED"]}
                value={status}
                onChange={(e) => {
                  setStatus(e.target.value);
                  setPage(1);
                }}
              />
            </div>

            {invoices.isLoading ? (
              <Spinner label="Loading invoices list…" />
            ) : (
              <Table<Invoice>
                rows={invoices.data?.items ?? []}
                onRowClick={(i) => setParams({ open: i.id })}
                empty={<EmptyState title="No invoices found" />}
                columns={[
                  {
                    key: "n",
                    header: "Invoice Number",
                    render: (i) => (
                      <span className="font-semibold text-xs text-ink-950 font-mono">
                        {i.invoice_number}
                      </span>
                    ),
                  },
                  {
                    key: "c",
                    header: "Client Name",
                    render: (i) => (
                      <span className="text-xs font-semibold text-ink-900 hover:text-brand-700">
                        {i.client.name}
                      </span>
                    ),
                  },
                  {
                    key: "d",
                    header: "Due Date",
                    render: (i) => <span className="text-xs text-ink-600 tabular-nums">{fmtDate(i.due_date)}</span>,
                  },
                  {
                    key: "t",
                    header: "Total Amount",
                    render: (i) => (
                      <span className="tabular-nums font-semibold text-xs text-ink-950">
                        {money(i.total)}
                      </span>
                    ),
                    className: "text-right",
                    headerClassName: "text-right",
                  },
                  {
                    key: "b",
                    header: "Balance Due",
                    render: (i) => (
                      <span
                        className={`tabular-nums font-semibold text-xs ${
                          Number(i.balance_due) > 0 ? "text-rose-700" : "text-emerald-700"
                        }`}
                      >
                        {money(i.balance_due)}
                      </span>
                    ),
                    className: "text-right",
                    headerClassName: "text-right",
                  },
                  {
                    key: "s",
                    header: "Status",
                    render: (i) => <Badge value={i.status} />,
                  },
                ]}
              />
            )}

            {invoices.data && (
              <Pagination page={page} pageSize={25} total={invoices.data.total} onPage={setPage} />
            )}
          </>
        )}

        {tab === "payments" && (
          <>
            {payments.isLoading ? (
              <Spinner label="Loading received payments…" />
            ) : (
              <Table<Payment>
                rows={payments.data?.items ?? []}
                empty={<EmptyState title="No payments recorded" />}
                columns={[
                  {
                    key: "c",
                    header: "Client",
                    render: (p) => <span className="text-xs font-semibold text-ink-900">{p.client.name}</span>,
                  },
                  {
                    key: "a",
                    header: "Amount Paid",
                    render: (p) => (
                      <span className="text-xs font-bold text-emerald-800 tabular-nums">
                        {money(p.amount)}
                      </span>
                    ),
                  },
                  {
                    key: "m",
                    header: "Payment Method",
                    render: (p) => (
                      <span className="text-xs text-ink-700 font-medium">
                        {humanize(p.method ?? p.provider)}
                      </span>
                    ),
                  },
                  {
                    key: "v",
                    header: "Verified Via",
                    render: (p) => (
                      <Badge value={p.verified_via} color="green" label={humanize(p.verified_via)} />
                    ),
                  },
                  {
                    key: "d",
                    header: "Payment Timestamp",
                    render: (p) => (
                      <span className="text-xs text-ink-500 tabular-nums">{fmtDateTime(p.paid_at)}</span>
                    ),
                  },
                ]}
              />
            )}

            {payments.data && (
              <Pagination page={page} pageSize={25} total={payments.data.total} onPage={setPage} />
            )}
          </>
        )}
      </Card>

      {/* Invoice Drawer Modal */}
      {openId && <InvoiceDrawer id={openId} onClose={() => setParams({})} />}

      <InvoiceFormModal open={creating} onClose={() => setCreating(false)} />
    </div>
  );
}

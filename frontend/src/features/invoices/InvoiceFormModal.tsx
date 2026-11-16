import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { ClientPicker } from "../../components/ClientPicker";
import { Button, ErrorBox, Input, Modal } from "../../components/ui";
import { useToast } from "../../hooks/useToast";
import { errorMessage } from "../../services/api";
import { billingApi } from "../../services/endpoints";
import { money } from "../../utils/format";

export interface Line {
  description: string;
  sac_code: string;
  quantity: string;
  unit_price: string;
  tax_rate: string;
}

const blank: Line = {
  description: "",
  sac_code: "",
  quantity: "1",
  unit_price: "",
  tax_rate: "18",
};

export function computeTotals(lines: Line[]) {
  let subtotal = 0;
  let tax = 0;
  for (const l of lines) {
    const amt = Math.round(Number(l.quantity || 0) * Number(l.unit_price || 0) * 100) / 100;
    subtotal += amt;
    tax += Math.round(amt * Number(l.tax_rate || 0)) / 100;
  }
  return { subtotal, tax, total: subtotal + tax };
}

export function InvoiceFormModal({
  open,
  onClose,
  clientId,
}: {
  open: boolean;
  onClose: () => void;
  clientId?: string;
}) {
  const qc = useQueryClient();
  const toast = useToast();
  const [client, setClient] = useState(clientId ?? "");
  const [due, setDue] = useState("");
  const [lines, setLines] = useState<Line[]>([{ ...blank }]);
  const totals = useMemo(() => computeTotals(lines), [lines]);

  const m = useMutation({
    mutationFn: () =>
      billingApi.create({
        client_id: client,
        due_date: due || null,
        items: lines
          .filter((l) => l.description && l.unit_price)
          .map((l) => ({ ...l, sac_code: l.sac_code || null })),
      }),
    onSuccess: (inv) => {
      qc.invalidateQueries({ queryKey: ["invoices"] });
      toast("success", `Invoice ${inv.invoice_number} created as draft`);
      onClose();
      setLines([{ ...blank }]);
    },
  });

  const upd = (i: number, k: keyof Line, v: string) =>
    setLines(lines.map((l, j) => (j === i ? { ...l, [k]: v } : l)));

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Create New Invoice"
      subtitle="Prepare professional GST tax invoice with automatic calculations"
      wide
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button
            disabled={!client || totals.total <= 0}
            loading={m.isPending}
            onClick={() => m.mutate()}
            className="shadow-sm"
          >
            Create draft
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        {m.error && <ErrorBox error={new Error(errorMessage(m.error))} />}

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
          {!clientId && <ClientPicker value={client} onChange={setClient} />}
          <Input
            label="Due date"
            type="date"
            value={due}
            onChange={(e) => setDue(e.target.value)}
            hint="Defaults to your practice payment terms"
          />
        </div>

        {/* Line Items Table */}
        <div className="rounded-xl border border-ink-200/90 overflow-hidden shadow-2xs">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-ink-100 bg-ink-50/70 text-left font-semibold uppercase tracking-wider text-ink-500">
                <th className="px-3 py-2.5">Description</th>
                <th className="w-24 px-2 py-2.5">SAC</th>
                <th className="w-16 px-2 py-2.5">Qty</th>
                <th className="w-28 px-2 py-2.5">Rate (₹)</th>
                <th className="w-20 px-2 py-2.5">GST %</th>
                <th className="w-10 px-2 py-2.5" />
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-100/80 bg-white">
              {lines.map((l, i) => (
                <tr key={i} className="hover:bg-ink-50/40">
                  <td className="p-2">
                    <input
                      aria-label="Description"
                      placeholder="e.g. Audit fee, Tax Advisory"
                      className="w-full rounded-lg border border-ink-200 bg-white px-2.5 py-1.5 text-xs text-ink-900 focus:border-brand-600 focus:outline-none focus:ring-1 focus:ring-brand-500"
                      value={l.description}
                      onChange={(e) => upd(i, "description", e.target.value)}
                    />
                  </td>
                  <td className="p-2">
                    <input
                      aria-label="SAC"
                      placeholder="998311"
                      className="w-full rounded-lg border border-ink-200 bg-white px-2.5 py-1.5 text-xs font-mono text-ink-900 focus:border-brand-600 focus:outline-none focus:ring-1 focus:ring-brand-500"
                      value={l.sac_code}
                      onChange={(e) => upd(i, "sac_code", e.target.value)}
                    />
                  </td>
                  <td className="p-2">
                    <input
                      aria-label="Quantity"
                      type="number"
                      min="0"
                      step="0.01"
                      className="w-full rounded-lg border border-ink-200 bg-white px-2.5 py-1.5 text-xs text-ink-900 focus:border-brand-600 focus:outline-none focus:ring-1 focus:ring-brand-500 tabular-nums"
                      value={l.quantity}
                      onChange={(e) => upd(i, "quantity", e.target.value)}
                    />
                  </td>
                  <td className="p-2">
                    <input
                      aria-label="Rate"
                      type="number"
                      min="0"
                      step="0.01"
                      placeholder="0.00"
                      className="w-full rounded-lg border border-ink-200 bg-white px-2.5 py-1.5 text-xs text-ink-900 focus:border-brand-600 focus:outline-none focus:ring-1 focus:ring-brand-500 tabular-nums font-semibold"
                      value={l.unit_price}
                      onChange={(e) => upd(i, "unit_price", e.target.value)}
                    />
                  </td>
                  <td className="p-2">
                    <input
                      aria-label="GST rate"
                      type="number"
                      min="0"
                      max="28"
                      className="w-full rounded-lg border border-ink-200 bg-white px-2.5 py-1.5 text-xs text-ink-900 focus:border-brand-600 focus:outline-none focus:ring-1 focus:ring-brand-500 tabular-nums"
                      value={l.tax_rate}
                      onChange={(e) => upd(i, "tax_rate", e.target.value)}
                    />
                  </td>
                  <td className="p-2 text-center">
                    <Button
                      size="xs"
                      variant="ghost"
                      aria-label="Remove line"
                      disabled={lines.length === 1}
                      onClick={() => setLines(lines.filter((_, j) => j !== i))}
                      className="text-ink-400 hover:text-rose-600"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="flex items-center justify-between">
          <Button
            size="xs"
            variant="outline"
            onClick={() => setLines([...lines, { ...blank }])}
            className="gap-1 text-xs"
          >
            <Plus className="h-3.5 w-3.5" />
            <span>Add line item</span>
          </Button>

          {/* Invoice Summary Box */}
          <div
            className="w-64 rounded-xl border border-ink-200/90 bg-ink-50/50 p-3.5 space-y-1.5 text-xs"
            data-testid="invoice-totals"
          >
            <div className="flex justify-between text-ink-500">
              <span>Subtotal</span>
              <span className="tabular-nums font-medium text-ink-800">{money(totals.subtotal)}</span>
            </div>
            <div className="flex justify-between text-ink-500">
              <span>GST Total</span>
              <span className="tabular-nums font-medium text-ink-800">{money(totals.tax)}</span>
            </div>
            <div className="flex justify-between border-t border-ink-200/80 pt-1.5 text-xs font-bold text-ink-950">
              <span>Total Invoice Amount</span>
              <span className="tabular-nums text-sm text-brand-900">{money(totals.total)}</span>
            </div>
          </div>
        </div>
      </div>
    </Modal>
  );
}

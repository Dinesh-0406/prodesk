import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { ClientPicker } from "../../components/ClientPicker";
import { Button, ErrorBox, Input, Modal, Select, Textarea } from "../../components/ui";
import { useToast } from "../../hooks/useToast";
import { errorMessage } from "../../services/api";
import { requestApi } from "../../services/endpoints";
import { DOCUMENT_TYPES } from "../../utils/format";

const PRESETS: Record<string, { name: string; document_type: string }[]> = {
  "ITR Filing": [
    { name: "Bank Statement", document_type: "BANK_STATEMENT" },
    { name: "Form 16", document_type: "TDS_DOCUMENT" },
    { name: "Capital Gains Statement", document_type: "OTHER" },
    { name: "Previous ITR", document_type: "ITR_ACKNOWLEDGEMENT" },
  ],
  "GST Return": [
    { name: "Sales invoices", document_type: "INVOICE" },
    { name: "Purchase invoices", document_type: "INVOICE" },
    { name: "Bank Statement", document_type: "BANK_STATEMENT" },
  ],
  KYC: [
    { name: "PAN card", document_type: "PAN" },
    { name: "Aadhaar", document_type: "AADHAAR" },
  ],
};

export function RequestFormModal({
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
  const [title, setTitle] = useState("ITR Filing");
  const [due, setDue] = useState("");
  const [instructions, setInstructions] = useState("");
  const [notify, setNotify] = useState(true);
  const [items, setItems] = useState(PRESETS["ITR Filing"]);

  const m = useMutation({
    mutationFn: () =>
      requestApi.create({
        client_id: client,
        title,
        due_date: due || null,
        instructions: instructions || null,
        items: items.filter((i) => i.name.trim()),
        notify_client: notify,
      }),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ["requests"] });
      qc.invalidateQueries({ queryKey: ["client-summary"] });
      toast(
        "success",
        r.notified_at ? "Document request checklist sent to client on WhatsApp" : "Request created"
      );
      onClose();
    },
  });

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Request Client Documents"
      subtitle="Clients receive interactive checklist via WhatsApp and client portal"
      wide
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button
            disabled={!client || !items.length}
            loading={m.isPending}
            onClick={() => m.mutate()}
            className="shadow-sm"
          >
            Create request
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        {m.error && <ErrorBox error={new Error(errorMessage(m.error))} />}

        {!clientId && <ClientPicker value={client} onChange={setClient} />}

        {/* Quick Checklists Templates */}
        <div>
          <span className="text-xs font-semibold text-ink-700 block mb-1.5">
            Load Quick Template Checklist
          </span>
          <div className="flex flex-wrap gap-2">
            {Object.keys(PRESETS).map((p) => (
              <Button
                key={p}
                size="xs"
                variant={title === p ? "subtle" : "outline"}
                onClick={() => {
                  setTitle(p);
                  setItems(PRESETS[p]);
                }}
              >
                {p} checklist
              </Button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3.5">
          <Input label="Title" value={title} onChange={(e) => setTitle(e.target.value)} />
          <Input
            label="Due date"
            type="date"
            value={due}
            onChange={(e) => setDue(e.target.value)}
          />
        </div>

        {/* Dynamic Items List */}
        <div className="space-y-2">
          <p className="text-xs font-semibold text-ink-700">Required Documents</p>
          <div className="space-y-2">
            {items.map((it, i) => (
              <div key={i} className="flex items-center gap-2">
                <input
                  aria-label={`Document ${i + 1}`}
                  placeholder="e.g. Bank statement for FY 25-26"
                  className="flex-1 rounded-lg border border-ink-200 bg-white px-3 py-1.5 text-xs text-ink-900 focus:border-brand-600 focus:outline-none focus:ring-1 focus:ring-brand-500"
                  value={it.name}
                  onChange={(e) =>
                    setItems(items.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))
                  }
                />
                <Select
                  aria-label="Type"
                  className="w-48 text-xs h-8"
                  options={DOCUMENT_TYPES}
                  value={it.document_type}
                  onChange={(e) =>
                    setItems(items.map((x, j) => (j === i ? { ...x, document_type: e.target.value } : x)))
                  }
                />
                <Button
                  size="xs"
                  variant="ghost"
                  aria-label="Remove"
                  disabled={items.length === 1}
                  onClick={() => setItems(items.filter((_, j) => j !== i))}
                  className="text-ink-400 hover:text-rose-600"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            ))}
          </div>
          <Button
            size="xs"
            variant="outline"
            onClick={() => setItems([...items, { name: "", document_type: "OTHER" }])}
            className="gap-1 mt-1 text-xs"
          >
            <Plus className="h-3.5 w-3.5" />
            <span>Add document</span>
          </Button>
        </div>

        <Textarea
          label="Instructions for the client"
          placeholder="e.g. Please provide password if statements are protected by password..."
          value={instructions}
          onChange={(e) => setInstructions(e.target.value)}
        />

        <div className="rounded-xl border border-brand-200/80 bg-brand-50/40 p-3">
          <label className="flex items-center gap-2 cursor-pointer text-xs font-medium text-brand-950">
            <input
              type="checkbox"
              className="h-4 w-4 rounded border-brand-300 text-brand-600 focus:ring-brand-500"
              checked={notify}
              onChange={(e) => setNotify(e.target.checked)}
            />
            <span>
              Notify client immediately on WhatsApp with official interactive checklist template
            </span>
          </label>
        </div>
      </div>
    </Modal>
  );
}

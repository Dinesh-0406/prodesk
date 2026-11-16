import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Button, ErrorBox, Input, Modal, Select, Textarea } from "../../components/ui";
import { useAuth } from "../../hooks/useAuth";
import { useToast } from "../../hooks/useToast";
import { errorMessage } from "../../services/api";
import { clientApi, orgApi } from "../../services/endpoints";
import type { Client } from "../../types";
import { CLIENT_TYPES } from "../../utils/format";

type FormState = {
  name: string;
  phone: string;
  email: string;
  client_type: string;
  pan: string;
  gstin: string;
  address: string;
  assigned_employee_id: string;
  notes: string;
  whatsapp_opt_in: boolean;
};

const empty: FormState = {
  name: "",
  phone: "",
  email: "",
  client_type: "INDIVIDUAL",
  pan: "",
  gstin: "",
  address: "",
  assigned_employee_id: "",
  notes: "",
  whatsapp_opt_in: true,
};

export function ClientFormModal({
  open,
  onClose,
  client,
  onSaved,
}: {
  open: boolean;
  onClose: () => void;
  client?: Client;
  onSaved?: (c: Client) => void;
}) {
  const qc = useQueryClient();
  const toast = useToast();
  const { can } = useAuth();
  const [f, setF] = useState<FormState>(() =>
    client
      ? {
          name: client.name,
          phone: client.phone,
          email: client.email ?? "",
          client_type: client.client_type,
          pan: client.pan ?? "",
          gstin: client.gstin ?? "",
          address: client.address ?? "",
          assigned_employee_id: client.assigned_employee_id ?? "",
          notes: client.notes ?? "",
          whatsapp_opt_in: client.whatsapp_opt_in,
        }
      : empty
  );

  const { data: users = [] } = useQuery({
    queryKey: ["users"],
    queryFn: orgApi.users,
    enabled: open,
  });

  const m = useMutation({
    mutationFn: () => {
      const body = {
        ...f,
        email: f.email || null,
        pan: f.pan || null,
        gstin: f.gstin || null,
        assigned_employee_id: f.assigned_employee_id || null,
      } as unknown as Partial<Client>;
      if (client && !can("TASK_ASSIGN")) {
        delete (body as Record<string, unknown>).assigned_employee_id;
      }
      return client ? clientApi.update(client.id, body) : clientApi.create(body);
    },
    onSuccess: (c) => {
      qc.invalidateQueries({ queryKey: ["clients"] });
      qc.invalidateQueries({ queryKey: ["client", c.id] });
      toast("success", client ? "Client profile updated" : `${c.name} added to practice`);
      onSaved?.(c);
      onClose();
      if (!client) setF(empty);
    },
  });

  const set = (k: keyof FormState) => (e: { target: { value: string } }) =>
    setF({ ...f, [k]: e.target.value });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    m.mutate();
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={client ? `Edit ${client.name}` : "Add New Client"}
      subtitle={
        client
          ? "Update contact details, statutory IDs, and assignments"
          : "Register client profile and record explicit WhatsApp communications consent"
      }
      wide
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button form="client-form" type="submit" loading={m.isPending} className="shadow-sm">
            Save client
          </Button>
        </>
      }
    >
      <form id="client-form" onSubmit={submit} className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {m.error && (
          <div className="sm:col-span-2">
            <ErrorBox error={new Error(errorMessage(m.error))} />
          </div>
        )}

        <Input
          label="Client name"
          required
          placeholder="e.g. Rahul Mehta or Apex Traders"
          value={f.name}
          onChange={set("name")}
        />

        <Input
          label="Mobile (WhatsApp)"
          required
          placeholder="98765 43210"
          value={f.phone}
          onChange={set("phone")}
          hint="Indian mobile; automatically normalised to +91 format"
        />

        <Select
          label="Client type"
          options={CLIENT_TYPES}
          value={f.client_type}
          onChange={set("client_type")}
        />

        <Input
          label="Email"
          type="email"
          placeholder="client@example.com"
          value={f.email}
          onChange={set("email")}
        />

        <Input
          label="PAN"
          maxLength={10}
          value={f.pan}
          onChange={(e) => setF({ ...f, pan: e.target.value.toUpperCase() })}
          placeholder="ABCDE1234F"
          className="font-mono uppercase"
        />

        <Input
          label="GSTIN"
          maxLength={15}
          value={f.gstin}
          onChange={(e) => setF({ ...f, gstin: e.target.value.toUpperCase() })}
          placeholder="27ABCDE1234F1Z5"
          className="font-mono uppercase"
        />

        <Select
          label="Assigned employee"
          placeholder="Unassigned"
          options={users
            .filter((u) => u.is_active)
            .map((u) => ({ value: u.id, label: u.full_name }))}
          value={f.assigned_employee_id}
          onChange={set("assigned_employee_id")}
          disabled={!!client && !can("TASK_ASSIGN")}
        />

        <Input
          label="Address"
          placeholder="Office or residential address"
          value={f.address}
          onChange={set("address")}
        />

        <div className="sm:col-span-2">
          <Textarea
            label="Notes"
            placeholder="Special filing instructions, preferences or history..."
            value={f.notes}
            onChange={set("notes")}
          />
        </div>

        <div className="sm:col-span-2 rounded-xl border border-brand-200/80 bg-brand-50/40 p-3.5">
          <label className="flex items-start gap-2.5 cursor-pointer text-xs font-medium text-brand-950">
            <input
              type="checkbox"
              className="mt-0.5 h-4 w-4 rounded border-brand-300 text-brand-600 focus:ring-brand-500"
              checked={f.whatsapp_opt_in}
              onChange={(e) => setF({ ...f, whatsapp_opt_in: e.target.checked })}
            />
            <div className="space-y-0.5">
              <span>
                Client has agreed to receive WhatsApp updates from the firm{" "}
                <span className="text-brand-700 font-semibold">(recorded in the consent log)</span>
              </span>
              <p className="text-[11px] text-brand-800/80 font-normal">
                Required for sending automated OTP delivery links, invoice payment reminders and tax filing status.
              </p>
            </div>
          </label>
        </div>
      </form>
    </Modal>
  );
}

export function ImportClientsModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const qc = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const m = useMutation({
    mutationFn: () => clientApi.import(file as File),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["clients"] }),
  });

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Import Clients from CSV"
      subtitle="Bulk upload your client directory in seconds"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Close
          </Button>
          <Button disabled={!file} loading={m.isPending} onClick={() => m.mutate()}>
            Import
          </Button>
        </>
      }
    >
      <div className="space-y-4 text-xs">
        <p className="text-ink-600 leading-relaxed">
          Columns supported:{" "}
          <code className="rounded-md bg-ink-100 px-1.5 py-0.5 text-xs font-mono text-ink-800">
            name, phone, email, client_type, pan, gstin, address, assigned_employee_email, whatsapp_opt_in, notes
          </code>
          . Only <b className="text-ink-950">name</b> and <b className="text-ink-950">phone</b> are required.
        </p>

        <div className="rounded-xl border border-ink-200 bg-ink-50/50 p-4">
          <input
            type="file"
            accept=".csv,text/csv"
            aria-label="CSV file"
            className="text-xs text-ink-700 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-brand-50 file:text-brand-700 hover:file:bg-brand-100 cursor-pointer"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </div>

        {m.error && <ErrorBox error={new Error(errorMessage(m.error))} />}

        {m.data && (
          <div className="rounded-xl border border-emerald-200 bg-emerald-50/70 p-3.5 space-y-1.5">
            <p className="text-xs font-semibold text-emerald-950">
              <b>{m.data.created}</b> clients created successfully · <b>{m.data.skipped}</b> skipped
            </p>
            {m.data.errors.slice(0, 8).map((e) => (
              <p key={e.row} className="text-xs text-rose-700">
                Row {e.row}: {e.error}
              </p>
            ))}
          </div>
        )}
      </div>
    </Modal>
  );
}

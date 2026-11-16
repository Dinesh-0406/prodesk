import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ClientPicker } from "../../components/ClientPicker";
import { Button, ErrorBox, Input, Modal, Select, Textarea } from "../../components/ui";
import { useAuth } from "../../hooks/useAuth";
import { useToast } from "../../hooks/useToast";
import { errorMessage } from "../../services/api";
import { orgApi, taskApi } from "../../services/endpoints";
import { PRIORITIES, SERVICE_TYPES, financialYears } from "../../utils/format";

export function TaskFormModal({
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
  const { can } = useAuth();
  const [f, setF] = useState({
    client_id: clientId ?? "",
    title: "",
    description: "",
    service_type: "ITR",
    financial_year: financialYears()[1],
    priority: "MEDIUM",
    due_date: "",
    assigned_employee_id: "",
  });

  const { data: users = [] } = useQuery({
    queryKey: ["users"],
    queryFn: orgApi.users,
    enabled: open && can("TASK_ASSIGN"),
  });

  const m = useMutation({
    mutationFn: () =>
      taskApi.create({
        ...f,
        due_date: f.due_date || null,
        assigned_employee_id: f.assigned_employee_id || null,
        financial_year: f.financial_year || null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tasks"] });
      qc.invalidateQueries({ queryKey: ["client-summary"] });
      toast("success", "Task created successfully");
      onClose();
      setF({
        client_id: clientId ?? "",
        title: "",
        description: "",
        service_type: "ITR",
        financial_year: financialYears()[1],
        priority: "MEDIUM",
        due_date: "",
        assigned_employee_id: "",
      });
    },
  });

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Create New Task"
      subtitle="Schedule statutory filing, advisory work or compliance review"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button
            disabled={!f.client_id || f.title.length < 2}
            loading={m.isPending}
            onClick={() => m.mutate()}
            className="shadow-sm"
          >
            Create task
          </Button>
        </>
      }
    >
      <div className="grid grid-cols-2 gap-3.5">
        {m.error && (
          <div className="col-span-2">
            <ErrorBox error={new Error(errorMessage(m.error))} />
          </div>
        )}

        {!clientId && (
          <div className="col-span-2">
            <ClientPicker value={f.client_id} onChange={(id) => setF({ ...f, client_id: id })} />
          </div>
        )}

        <div className="col-span-2">
          <Input
            label="Title"
            placeholder="e.g. ITR-3 Filing FY 2025-26 or GST Q3 Reconciliation"
            value={f.title}
            onChange={(e) => setF({ ...f, title: e.target.value })}
          />
        </div>

        <Select
          label="Service"
          options={SERVICE_TYPES}
          value={f.service_type}
          onChange={(e) => setF({ ...f, service_type: e.target.value })}
        />

        <Select
          label="Financial year"
          placeholder="—"
          options={financialYears()}
          value={f.financial_year}
          onChange={(e) => setF({ ...f, financial_year: e.target.value })}
        />

        <Select
          label="Priority"
          options={PRIORITIES}
          value={f.priority}
          onChange={(e) => setF({ ...f, priority: e.target.value })}
        />

        <Input
          label="Due date"
          type="date"
          value={f.due_date}
          onChange={(e) => setF({ ...f, due_date: e.target.value })}
        />

        {can("TASK_ASSIGN") && (
          <div className="col-span-2">
            <Select
              label="Assign to"
              placeholder="Client's assigned employee"
              value={f.assigned_employee_id}
              options={users
                .filter((u) => u.is_active)
                .map((u) => ({ value: u.id, label: u.full_name }))}
              onChange={(e) => setF({ ...f, assigned_employee_id: e.target.value })}
            />
          </div>
        )}

        <div className="col-span-2">
          <Textarea
            label="Description"
            placeholder="Key filing requirements, notes, turnover limits or references..."
            value={f.description}
            onChange={(e) => setF({ ...f, description: e.target.value })}
          />
        </div>
      </div>
    </Modal>
  );
}

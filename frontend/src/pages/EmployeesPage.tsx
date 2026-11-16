import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Clock, Mail, Shield, ShieldAlert, UserCheck, UserPlus, Users } from "lucide-react";
import { useMemo, useState } from "react";
import { Avatar, Badge, Button, Card, EmptyState, ErrorBox, Field, Input, Modal, PageHeader, Select, Spinner, Table } from "../components/ui";
import { useAuth } from "../hooks/useAuth";
import { useToast } from "../hooks/useToast";
import { errorMessage } from "../services/api";
import { orgApi } from "../services/endpoints";
import type { User } from "../types";
import { fmtDateTime } from "../utils/format";

const ROLES = [
  { value: "FIRM_ADMIN", label: "Firm Admin", desc: "Full administrative & billing control" },
  { value: "PARTNER", label: "Partner", desc: "All clients, reports & firm oversight" },
  { value: "MANAGER", label: "Manager", desc: "Team workflow, clients & invoices" },
  { value: "EMPLOYEE", label: "Employee", desc: "Assigned client tasks & documents" },
];

export function EmployeesPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const { me } = useAuth();
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ email: "", full_name: "", role: "EMPLOYEE" });

  const { data: users, isLoading } = useQuery({ queryKey: ["users"], queryFn: orgApi.users });

  const invite = useMutation({
    mutationFn: () => orgApi.invite(f),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["users"] });
      setOpen(false);
      toast("success", `Invitation sent to ${f.email}`);
      setF({ email: "", full_name: "", role: "EMPLOYEE" });
    },
    onError: (e) => toast("error", errorMessage(e)),
  });

  const update = useMutation({
    mutationFn: (a: { id: string; body: { role?: string; is_active?: boolean } }) => orgApi.updateUser(a.id, a.body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["users"] });
      toast("success", "User settings updated");
    },
    onError: (e) => toast("error", errorMessage(e)),
  });

  const stats = useMemo(() => {
    const list = users ?? [];
    return {
      total: list.length,
      active: list.filter((u) => u.is_active && u.is_verified).length,
      pending: list.filter((u) => u.is_active && !u.is_verified).length,
      admins: list.filter((u) => u.role_name === "FIRM_ADMIN" || u.role_name === "PARTNER").length,
    };
  }, [users]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Team & Access"
        subtitle="Manage firm members, role hierarchies, and workspace access privileges."
        actions={
          <Button onClick={() => setOpen(true)}>
            <UserPlus className="h-4 w-4" />
            Invite employee
          </Button>
        }
      />

      {/* Summary KPI Strip */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="flex items-center gap-3 rounded-xl border border-ink-200/80 bg-white p-3.5 shadow-card">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-ink-100 text-ink-700">
            <Users className="h-5 w-5" />
          </div>
          <div>
            <p className="text-xs font-medium uppercase tracking-wider text-ink-400">Total Team</p>
            <p className="text-xl font-semibold tabular-nums text-ink-950">{stats.total}</p>
          </div>
        </div>

        <div className="flex items-center gap-3 rounded-xl border border-ink-200/80 bg-white p-3.5 shadow-card">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-50 text-emerald-700">
            <UserCheck className="h-5 w-5" />
          </div>
          <div>
            <p className="text-xs font-medium uppercase tracking-wider text-ink-400">Active</p>
            <p className="text-xl font-semibold tabular-nums text-ink-950">{stats.active}</p>
          </div>
        </div>

        <div className="flex items-center gap-3 rounded-xl border border-ink-200/80 bg-white p-3.5 shadow-card">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-50 text-amber-700">
            <Clock className="h-5 w-5" />
          </div>
          <div>
            <p className="text-xs font-medium uppercase tracking-wider text-ink-400">Pending Invite</p>
            <p className="text-xl font-semibold tabular-nums text-ink-950">{stats.pending}</p>
          </div>
        </div>

        <div className="flex items-center gap-3 rounded-xl border border-ink-200/80 bg-white p-3.5 shadow-card">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-50 text-brand-700">
            <Shield className="h-5 w-5" />
          </div>
          <div>
            <p className="text-xs font-medium uppercase tracking-wider text-ink-400">Admins & Partners</p>
            <p className="text-xl font-semibold tabular-nums text-ink-950">{stats.admins}</p>
          </div>
        </div>
      </div>

      <Card padded={false}>
        {isLoading ? (
          <div className="p-8">
            <Spinner />
          </div>
        ) : !users?.length ? (
          <EmptyState
            icon={<Users className="h-8 w-8" />}
            title="No employees found"
            description="Invite colleagues to collaborate on client tasks and documents."
            action={
              <Button onClick={() => setOpen(true)}>
                <UserPlus className="h-4 w-4" />
                Invite employee
              </Button>
            }
          />
        ) : (
          <Table<User>
            rows={users}
            columns={[
              {
                key: "n",
                header: "Member",
                render: (u) => (
                  <div className="flex items-center gap-3 py-1">
                    <Avatar name={u.full_name} size="md" />
                    <div>
                      <p className="text-sm font-medium text-ink-950">
                        {u.full_name}
                        {u.id === me?.id && (
                          <span className="ml-2 inline-flex items-center rounded bg-brand-50 px-1.5 py-0.5 text-[10px] font-semibold text-brand-700">
                            You
                          </span>
                        )}
                      </p>
                      <p className="flex items-center gap-1.5 text-xs text-ink-500">
                        <Mail className="h-3 w-3 text-ink-400" />
                        {u.email}
                      </p>
                    </div>
                  </div>
                ),
              },
              {
                key: "r",
                header: "Role & Permissions",
                render: (u) => (
                  <div className="w-48">
                    <Select
                      aria-label={`Role for ${u.full_name}`}
                      disabled={u.id === me?.id}
                      value={u.role_name}
                      options={ROLES.map((r) => ({ value: r.value, label: r.label }))}
                      onChange={(e) => update.mutate({ id: u.id, body: { role: e.target.value } })}
                    />
                  </div>
                ),
              },
              {
                key: "s",
                header: "Status",
                render: (u) => (
                  <Badge
                    value={!u.is_active ? "INACTIVE" : u.is_verified ? "ACTIVE" : "PENDING"}
                    label={!u.is_active ? "Deactivated" : u.is_verified ? "Active" : "Invited"}
                  />
                ),
              },
              {
                key: "l",
                header: "Last Active",
                render: (u) => (
                  <span className="text-xs tabular-nums text-ink-500">
                    {u.last_login_at ? fmtDateTime(u.last_login_at) : "Never signed in"}
                  </span>
                ),
              },
              {
                key: "a",
                header: "",
                render: (u) =>
                  u.id !== me?.id ? (
                    <div className="flex justify-end">
                      <Button
                        size="sm"
                        variant={u.is_active ? "ghost" : "secondary"}
                        className={u.is_active ? "text-ink-600 hover:text-rose-600" : ""}
                        onClick={() => update.mutate({ id: u.id, body: { is_active: !u.is_active } })}
                      >
                        {u.is_active ? "Deactivate" : "Reactivate"}
                      </Button>
                    </div>
                  ) : null,
              },
            ]}
          />
        )}
      </Card>

      {/* Role explanation drawer/card */}
      <div className="rounded-xl border border-ink-200/80 bg-ink-50/50 p-4">
        <h4 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-ink-500">
          <ShieldAlert className="h-3.5 w-3.5" />
          Access Level Reference
        </h4>
        <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {ROLES.map((r) => (
            <div key={r.value} className="rounded-lg border border-ink-200/60 bg-white p-3 shadow-xs">
              <p className="text-xs font-semibold text-ink-900">{r.label}</p>
              <p className="mt-0.5 text-xs text-ink-500">{r.desc}</p>
            </div>
          ))}
        </div>
      </div>

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="Invite team member"
        description="An email with an account activation link will be sent. The link expires in 7 days."
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button loading={invite.isPending} onClick={() => invite.mutate()}>
              Send invite
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          {invite.error && <ErrorBox error={new Error(errorMessage(invite.error))} />}
          <Input
            label="Full name"
            required
            placeholder="e.g. Priya Sharma"
            value={f.full_name}
            onChange={(e) => setF({ ...f, full_name: e.target.value })}
          />
          <Input
            label="Email"
            type="email"
            required
            placeholder="colleague@yourfirm.com"
            value={f.email}
            onChange={(e) => setF({ ...f, email: e.target.value })}
          />
          <Field label="Role" hint="Determines client data visibility and administrative power">
            <Select
              options={ROLES.map((r) => ({ value: r.value, label: `${r.label} — ${r.desc}` }))}
              value={f.role}
              onChange={(e) => setF({ ...f, role: e.target.value })}
            />
          </Field>
          <div className="rounded-lg bg-emerald-50/60 p-3 text-xs text-emerald-800">
            <div className="flex items-start gap-2">
              <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-600" />
              <span>Employees only see clients assigned to them. Managers, Partners, and Admins can access all clients.</span>
            </div>
          </div>
        </div>
      </Modal>
    </div>
  );
}

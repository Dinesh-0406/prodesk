import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  Building2,
  Check,
  CheckCircle2,
  MessageSquare,
  Sparkles,
  UserPlus,
  Users,
} from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button, Card, ErrorBox, Field, Input, Select, Spinner } from "../components/ui";
import { ClientFormModal } from "../features/clients/ClientForm";
import { errorMessage } from "../services/api";
import { orgApi, whatsappApi } from "../services/endpoints";
import { cn } from "../utils/format";

const STEPS = [
  { key: "FIRM_PROFILE", label: "Firm profile", icon: Building2 },
  { key: "WHATSAPP_SETUP", label: "WhatsApp setup", icon: MessageSquare },
  { key: "INVITE_EMPLOYEES", label: "Invite team", icon: Users },
  { key: "ADD_CLIENTS", label: "Add clients", icon: UserPlus },
  { key: "READY", label: "Ready", icon: Sparkles },
] as const;

export function OnboardingPage() {
  const qc = useQueryClient();
  const nav = useNavigate();
  const { data: org } = useQuery({ queryKey: ["org"], queryFn: orgApi.current });
  const [profile, setProfile] = useState<{ name?: string; phone?: string; address?: string }>({});
  const [wa, setWa] = useState({ provider: "mock", phone_number_id: "", display_phone_number: "", access_token: "" });
  const [invite, setInvite] = useState({ email: "", full_name: "", role: "EMPLOYEE" });
  const [clientOpen, setClientOpen] = useState(false);

  const advance = useMutation({
    mutationFn: async (step: string) => orgApi.update({ onboarding_step: step }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["org"] }),
  });

  const saveProfile = useMutation({
    mutationFn: () => orgApi.update({ ...profile, onboarding_step: "WHATSAPP_SETUP" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["org"] }),
  });

  const saveWa = useMutation({
    mutationFn: async () => {
      await whatsappApi.saveAccount({
        ...wa,
        access_token: wa.access_token || undefined,
        phone_number_id: wa.phone_number_id || `mock-${org?.slug}`,
      });
      return orgApi.update({ onboarding_step: "INVITE_EMPLOYEES" });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["org"] }),
  });

  const sendInvite = useMutation({
    mutationFn: () => orgApi.invite(invite),
    onSuccess: () => setInvite({ email: "", full_name: "", role: "EMPLOYEE" }),
  });

  if (!org) {
    return (
      <div className="flex h-96 items-center justify-center">
        <Spinner />
      </div>
    );
  }

  const idx = STEPS.findIndex((s) => s.key === org.onboarding_step);
  const step = org.onboarding_step;
  const err = saveProfile.error || saveWa.error || sendInvite.error || advance.error;

  return (
    <div className="mx-auto max-w-2xl py-6">
      {/* Header */}
      <div className="text-center">
        <div className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-50 text-brand-700 shadow-xs mb-3">
          <Sparkles className="h-6 w-6" />
        </div>
        <h1 className="text-2xl font-semibold tracking-tight text-ink-950">Set up {org.name}</h1>
        <p className="mt-1 text-sm text-ink-500">
          Complete a few quick steps to configure your practice and automate client communication.
        </p>
      </div>

      {/* Stepper Navigation */}
      <nav aria-label="Progress" className="mt-8">
        <ol className="flex items-center justify-between">
          {STEPS.map((s, i) => {
            const isDone = i < idx;
            const isCurrent = i === idx;
            return (
              <li key={s.key} className="relative flex flex-1 flex-col items-center">
                {i > 0 && (
                  <div
                    className={cn(
                      "absolute top-4 -left-1/2 right-1/2 h-0.5",
                      i <= idx ? "bg-brand-600" : "bg-ink-200"
                    )}
                  />
                )}
                <div
                  className={cn(
                    "relative z-10 flex h-8 w-8 items-center justify-center rounded-full text-xs font-semibold transition-colors",
                    isDone
                      ? "bg-brand-600 text-white"
                      : isCurrent
                      ? "border-2 border-brand-600 bg-white text-brand-700 shadow-xs ring-4 ring-brand-50"
                      : "border border-ink-300 bg-white text-ink-400"
                  )}
                >
                  {isDone ? <Check className="h-4 w-4" /> : i + 1}
                </div>
                <span
                  className={cn(
                    "mt-2 text-[11px] font-medium hidden sm:block",
                    isCurrent ? "text-brand-800 font-semibold" : isDone ? "text-ink-700" : "text-ink-400"
                  )}
                >
                  {s.label}
                </span>
              </li>
            );
          })}
        </ol>
      </nav>

      {/* Step Content Card */}
      <div className="mt-8">
        {err && (
          <div className="mb-4">
            <ErrorBox error={new Error(errorMessage(err))} />
          </div>
        )}

        {step === "FIRM_PROFILE" && (
          <Card
            title={
              <span className="flex items-center gap-2">
                <Building2 className="h-4 w-4 text-brand-700" />
                Firm Profile
              </span>
            }
            description="Verify your practice's contact details as they will appear on invoices and the client portal."
          >
            <div className="space-y-4">
              <Input
                label="Firm name"
                defaultValue={org.name}
                onChange={(e) => setProfile({ ...profile, name: e.target.value })}
              />
              <Input
                label="Office phone"
                placeholder="+91 98765 43210"
                defaultValue={org.phone ?? ""}
                onChange={(e) => setProfile({ ...profile, phone: e.target.value })}
              />
              <Input
                label="Address"
                placeholder="Office suite, building, street, city, pin code"
                defaultValue={org.address ?? ""}
                onChange={(e) => setProfile({ ...profile, address: e.target.value })}
              />
              <div className="flex justify-end pt-2">
                <Button loading={saveProfile.isPending} onClick={() => saveProfile.mutate()}>
                  Continue
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </Card>
        )}

        {step === "WHATSAPP_SETUP" && (
          <Card
            title={
              <span className="flex items-center gap-2">
                <MessageSquare className="h-4 w-4 text-emerald-600" />
                Connect WhatsApp (official Cloud API)
              </span>
            }
            description="Choose how you want to send automated tax reminders and document delivery notifications."
          >
            <div className="space-y-4">
              <div className="rounded-lg bg-emerald-50/70 p-3.5 text-xs text-emerald-900 border border-emerald-100">
                <p>
                  Use the <strong>Mock provider</strong> to explore and test immediately. Switch to Meta's official
                  WhatsApp Cloud API anytime in Settings once your WhatsApp Business Account is verified.
                </p>
              </div>

              <Field label="Provider">
                <Select
                  options={[
                    { value: "mock", label: "Mock (development / test mode)" },
                    { value: "meta", label: "Meta WhatsApp Cloud API" },
                  ]}
                  value={wa.provider}
                  onChange={(e) => setWa({ ...wa, provider: e.target.value })}
                />
              </Field>

              {wa.provider === "meta" && (
                <>
                  <Input
                    label="Phone number ID"
                    placeholder="e.g. 104857201928471"
                    value={wa.phone_number_id}
                    onChange={(e) => setWa({ ...wa, phone_number_id: e.target.value })}
                  />
                  <Input
                    label="Display phone number"
                    placeholder="+91 98765 43210"
                    value={wa.display_phone_number}
                    onChange={(e) => setWa({ ...wa, display_phone_number: e.target.value })}
                  />
                  <Input
                    label="Permanent access token"
                    type="password"
                    autoComplete="off"
                    placeholder="System user token from Meta Business Suite"
                    value={wa.access_token}
                    onChange={(e) => setWa({ ...wa, access_token: e.target.value })}
                    hint="Stored encrypted; never shown again."
                  />
                </>
              )}

              <div className="flex items-center justify-between pt-2">
                <Button variant="ghost" onClick={() => advance.mutate("INVITE_EMPLOYEES")}>
                  Skip for now
                </Button>
                <Button loading={saveWa.isPending} onClick={() => saveWa.mutate()}>
                  Save & continue
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </Card>
        )}

        {step === "INVITE_EMPLOYEES" && (
          <Card
            title={
              <span className="flex items-center gap-2">
                <Users className="h-4 w-4 text-brand-700" />
                Invite your team
              </span>
            }
            description="Add your partners, managers, and article assistants so they can manage their clients."
          >
            <div className="space-y-4">
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <Input
                  label="Name"
                  placeholder="e.g. Ananya Roy"
                  value={invite.full_name}
                  onChange={(e) => setInvite({ ...invite, full_name: e.target.value })}
                />
                <Input
                  label="Email"
                  type="email"
                  placeholder="ananya@firm.com"
                  value={invite.email}
                  onChange={(e) => setInvite({ ...invite, email: e.target.value })}
                />
                <Field label="Role">
                  <Select
                    options={["PARTNER", "MANAGER", "EMPLOYEE", "FIRM_ADMIN"]}
                    value={invite.role}
                    onChange={(e) => setInvite({ ...invite, role: e.target.value })}
                  />
                </Field>
              </div>

              {sendInvite.isSuccess && (
                <div className="flex items-center gap-2 rounded-lg bg-emerald-50 px-3 py-2 text-xs font-medium text-emerald-800">
                  <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                  Invitation email sent successfully.
                </div>
              )}

              <div className="flex items-center justify-between pt-2">
                <Button variant="secondary" loading={sendInvite.isPending} onClick={() => sendInvite.mutate()}>
                  Send invite
                </Button>
                <Button onClick={() => advance.mutate("ADD_CLIENTS")}>
                  Continue
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </Card>
        )}

        {step === "ADD_CLIENTS" && (
          <Card
            title={
              <span className="flex items-center gap-2">
                <UserPlus className="h-4 w-4 text-brand-700" />
                Add your first client
              </span>
            }
            description="Create your first client record to start tracking documents, tasks, and WhatsApp messages."
          >
            <div className="space-y-4">
              <p className="text-sm text-ink-600">
                You can add a client manually now, or import a batch CSV list later from the Clients workspace.
              </p>
              <div className="flex items-center justify-between pt-2">
                <Button variant="ghost" onClick={() => advance.mutate("READY")}>
                  Skip
                </Button>
                <Button onClick={() => setClientOpen(true)}>
                  <UserPlus className="h-4 w-4" />
                  Add client
                </Button>
              </div>
              <ClientFormModal
                open={clientOpen}
                onClose={() => setClientOpen(false)}
                onSaved={() => qc.invalidateQueries({ queryKey: ["org"] })}
              />
            </div>
          </Card>
        )}

        {step === "READY" && (
          <Card
            title={
              <span className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-brand-700" />
                You're all set
              </span>
            }
          >
            <div className="space-y-4 py-2">
              <div className="rounded-xl border border-emerald-200/80 bg-emerald-50/40 p-4">
                <p className="text-sm font-medium text-emerald-950">Your practice workspace is configured and ready.</p>
                <p className="mt-1 text-xs text-emerald-800">
                  You can now create tasks, request documents, generate GST-compliant invoices, and communicate securely with your clients.
                </p>
              </div>
              <div className="flex justify-end pt-2">
                <Button onClick={() => nav("/")}>
                  Go to dashboard
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}

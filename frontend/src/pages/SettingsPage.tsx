import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bell,
  Building2,
  CheckCircle2,
  FileCheck2,
  KeyRound,
  MessageSquare,
  Receipt,
  RefreshCw,
  Save,
  Sparkles,
} from "lucide-react";
import { useEffect, useState } from "react";
import {
  Badge,
  Button,
  Card,
  ErrorBox,
  Field,
  Input,
  KeyValue,
  PageHeader,
  Select,
  Spinner,
  Tabs,
  Textarea,
} from "../components/ui";
import { useToast } from "../hooks/useToast";
import { errorMessage } from "../services/api";
import { orgApi, whatsappApi } from "../services/endpoints";
import type { Organization, Template } from "../types";
import { fmtDateTime, humanize } from "../utils/format";

function FirmSettings({ org }: { org: Organization }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [f, setF] = useState({
    name: org.name,
    email: org.email ?? "",
    phone: org.phone ?? "",
    address: org.address ?? "",
    timezone: org.timezone,
  });
  const [wh, setWh] = useState(org.settings.working_hours);
  const [notif, setNotif] = useState(org.settings.notifications);
  const [rem, setRem] = useState(org.settings.reminders);
  const [inv, setInv] = useState(org.settings.invoice);
  const [faqs, setFaqs] = useState(JSON.stringify(org.settings.faqs ?? [], null, 2));

  const save = useMutation({
    mutationFn: () =>
      orgApi.update({
        ...f,
        email: f.email || null,
        phone: f.phone || null,
        working_hours: wh,
        notifications: notif,
        reminders: rem,
        invoice: inv,
        faqs: JSON.parse(faqs || "[]"),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["org"] });
      toast("success", "Firm settings saved successfully");
    },
    onError: (e) => toast("error", errorMessage(e)),
  });

  return (
    <div className="space-y-6">
      {/* Firm Profile Card */}
      <Card
        title={
          <span className="flex items-center gap-2">
            <Building2 className="h-4 w-4 text-brand-700" />
            Firm Profile
          </span>
        }
      >
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Input
            label="Firm name"
            required
            value={f.name}
            onChange={(e) => setF({ ...f, name: e.target.value })}
          />
          <Input
            label="Contact email"
            type="email"
            value={f.email}
            onChange={(e) => setF({ ...f, email: e.target.value })}
          />
          <Input
            label="Contact phone"
            value={f.phone}
            onChange={(e) => setF({ ...f, phone: e.target.value })}
          />
          <Input
            label="Timezone"
            value={f.timezone}
            onChange={(e) => setF({ ...f, timezone: e.target.value })}
          />
          <div className="sm:col-span-2">
            <Input
              label="Address"
              value={f.address}
              onChange={(e) => setF({ ...f, address: e.target.value })}
            />
          </div>
          <div>
            <Input
              label="Working hours start"
              type="time"
              value={wh.start}
              onChange={(e) => setWh({ ...wh, start: e.target.value })}
            />
          </div>
          <div>
            <Input
              label="Working hours end"
              type="time"
              value={wh.end}
              onChange={(e) => setWh({ ...wh, end: e.target.value })}
            />
          </div>

          <div className="rounded-lg border border-ink-200/80 bg-ink-50/60 p-3 sm:col-span-2">
            <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
              <span className="text-ink-600">
                Client Portal URL: <code className="rounded bg-white px-1.5 py-0.5 font-mono font-medium text-ink-900 border border-ink-200">/portal/login</code>
              </span>
              <span className="text-ink-600">
                Firm code: <b className="font-mono text-brand-700">{org.slug}</b>
              </span>
            </div>
          </div>
        </div>
      </Card>

      {/* Notifications & Reminders */}
      <Card
        title={
          <span className="flex items-center gap-2">
            <Bell className="h-4 w-4 text-brand-700" />
            Notifications & Automated Reminders
          </span>
        }
      >
        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-3 rounded-lg border border-ink-200/80 bg-ink-50/40 p-4 sm:grid-cols-2">
            <label className="flex items-center gap-2.5 text-sm font-medium text-ink-900 sm:col-span-2 cursor-pointer">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-ink-300 text-brand-600 focus:ring-brand-500"
                checked={notif.auto_deliver_on_approval}
                onChange={(e) => setNotif({ ...notif, auto_deliver_on_approval: e.target.checked })}
              />
              Automatically send approved documents to clients on WhatsApp
            </label>
            <label className="flex items-center gap-2.5 text-sm text-ink-800 cursor-pointer">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-ink-300 text-brand-600 focus:ring-brand-500"
                checked={rem.document_reminders_enabled}
                onChange={(e) => setRem({ ...rem, document_reminders_enabled: e.target.checked })}
              />
              Document reminders
            </label>
            <label className="flex items-center gap-2.5 text-sm text-ink-800 cursor-pointer">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-ink-300 text-brand-600 focus:ring-brand-500"
                checked={rem.invoice_reminders_enabled}
                onChange={(e) => setRem({ ...rem, invoice_reminders_enabled: e.target.checked })}
              />
              Payment reminders
            </label>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <Input
              label="Remind every (hours)"
              type="number"
              min={6}
              value={rem.frequency_hours}
              onChange={(e) => setRem({ ...rem, frequency_hours: Number(e.target.value) })}
            />
            <Input
              label="Max reminders per item"
              type="number"
              min={0}
              max={10}
              value={rem.max_reminders}
              onChange={(e) => setRem({ ...rem, max_reminders: Number(e.target.value) })}
            />
            <div className="grid grid-cols-2 gap-2">
              <Input
                label="Quiet from"
                type="time"
                value={rem.quiet_hours_start}
                onChange={(e) => setRem({ ...rem, quiet_hours_start: e.target.value })}
              />
              <Input
                label="Quiet until"
                type="time"
                value={rem.quiet_hours_end}
                onChange={(e) => setRem({ ...rem, quiet_hours_end: e.target.value })}
              />
            </div>
          </div>
        </div>
      </Card>

      {/* Invoice Settings */}
      <Card
        title={
          <span className="flex items-center gap-2">
            <Receipt className="h-4 w-4 text-brand-700" />
            Billing & Invoicing Configuration
          </span>
        }
      >
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
          <Input
            label="Number prefix"
            value={inv.prefix}
            placeholder="INV-"
            onChange={(e) => setInv({ ...inv, prefix: e.target.value })}
          />
          <Input
            label="Default GST %"
            type="number"
            value={inv.default_tax_rate}
            onChange={(e) => setInv({ ...inv, default_tax_rate: Number(e.target.value) })}
          />
          <Input
            label="Payment terms (days)"
            type="number"
            value={inv.payment_terms_days}
            onChange={(e) => setInv({ ...inv, payment_terms_days: Number(e.target.value) })}
          />
          <Input
            label="Firm GSTIN"
            value={inv.gstin}
            placeholder="27AAAAA0000A1Z5"
            onChange={(e) => setInv({ ...inv, gstin: e.target.value.toUpperCase() })}
          />
        </div>
      </Card>

      {/* Assistant FAQs */}
      <Card
        title={
          <span className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-brand-700" />
            Assistant FAQs & Knowledge Base
          </span>
        }
        description="Grounding questions and answers for client queries. ProDesk AI only answers strictly based on this list."
      >
        <Textarea
          aria-label="FAQs JSON"
          rows={7}
          className="font-mono text-xs"
          value={faqs}
          onChange={(e) => setFaqs(e.target.value)}
        />
      </Card>

      <div className="flex justify-end pt-2">
        <Button loading={save.isPending} onClick={() => save.mutate()}>
          <Save className="h-4 w-4" />
          Save settings
        </Button>
      </div>
    </div>
  );
}

function WhatsAppSettings() {
  const qc = useQueryClient();
  const toast = useToast();
  const { data: acc } = useQuery({ queryKey: ["wa-account"], queryFn: whatsappApi.account });
  const { data: templates = [] } = useQuery({ queryKey: ["templates"], queryFn: whatsappApi.templates });

  const [f, setF] = useState({
    provider: "mock",
    phone_number_id: "",
    display_phone_number: "",
    business_account_id: "",
    api_version: "",
    access_token: "",
    app_secret: "",
  });

  useEffect(() => {
    if (acc) {
      setF((x) => ({
        ...x,
        provider: acc.provider,
        phone_number_id: acc.phone_number_id ?? "",
        display_phone_number: acc.display_phone_number ?? "",
        business_account_id: acc.business_account_id ?? "",
        api_version: acc.api_version ?? "",
      }));
    }
  }, [acc]);

  const done = (m: string) => () => {
    qc.invalidateQueries({ queryKey: ["wa-account"] });
    qc.invalidateQueries({ queryKey: ["templates"] });
    toast("success", m);
  };
  const fail = (e: unknown) => toast("error", errorMessage(e));

  const save = useMutation({
    mutationFn: () =>
      whatsappApi.saveAccount({
        ...f,
        access_token: f.access_token || undefined,
        app_secret: f.app_secret || undefined,
        api_version: f.api_version || undefined,
      }),
    onSuccess: () => {
      setF({ ...f, access_token: "", app_secret: "" });
      done("WhatsApp settings saved")();
    },
    onError: fail,
  });

  const verify = useMutation({ mutationFn: whatsappApi.verify, onSuccess: done("Connection checked"), onError: fail });
  const sync = useMutation({ mutationFn: whatsappApi.syncTemplates, onSuccess: done("Template status synced from Meta"), onError: fail });
  const updTpl = useMutation({
    mutationFn: (a: { id: string; b: Partial<Template> }) => whatsappApi.updateTemplate(a.id, a.b),
    onSuccess: done("Template updated"),
    onError: fail,
  });

  if (!acc) return <Spinner />;

  return (
    <div className="space-y-6">
      {/* WhatsApp Cloud API Account */}
      <Card
        title={
          <span className="flex items-center gap-2">
            <MessageSquare className="h-4 w-4 text-emerald-600" />
            WhatsApp Business Platform (official Cloud API)
          </span>
        }
        actions={<Badge value={acc.status} />}
        description="Official Meta WhatsApp Business Cloud API integration for secure document and invoice notifications."
      >
        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Provider">
              <Select
                options={[
                  { value: "mock", label: "Mock (development simulation)" },
                  { value: "meta", label: "Meta WhatsApp Cloud API" },
                ]}
                value={f.provider}
                onChange={(e) => setF({ ...f, provider: e.target.value })}
              />
            </Field>
            <Input
              label="Phone number ID"
              placeholder="e.g. 104857201928471"
              value={f.phone_number_id}
              onChange={(e) => setF({ ...f, phone_number_id: e.target.value })}
            />
            <Input
              label="Display phone number"
              placeholder="+91 98765 43210"
              value={f.display_phone_number}
              onChange={(e) => setF({ ...f, display_phone_number: e.target.value })}
            />
            <Input
              label="WhatsApp Business Account ID"
              placeholder="e.g. 109283746501928"
              value={f.business_account_id}
              onChange={(e) => setF({ ...f, business_account_id: e.target.value })}
            />
            <Input
              label="Graph API version"
              placeholder="v21.0"
              value={f.api_version}
              onChange={(e) => setF({ ...f, api_version: e.target.value })}
            />
            <Input
              label={`Access token ${acc.access_token_set ? `(set: ${acc.access_token_hint})` : "(not set)"}`}
              type="password"
              autoComplete="off"
              placeholder="Leave blank to keep current"
              value={f.access_token}
              onChange={(e) => setF({ ...f, access_token: e.target.value })}
            />
            <div className="sm:col-span-2">
              <Input
                label={`App secret ${acc.app_secret_set ? "(set)" : "(optional, own Meta app)"}`}
                type="password"
                autoComplete="off"
                placeholder="Optional Meta app secret for signature validation"
                value={f.app_secret}
                onChange={(e) => setF({ ...f, app_secret: e.target.value })}
              />
            </div>
          </div>

          {/* Webhook & Diagnostic Info */}
          <div className="rounded-xl border border-ink-200/80 bg-ink-50/60 p-4">
            <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-ink-500">
              Webhook Configuration & Diagnostics
            </h4>
            <KeyValue
              items={[
                [
                  "Webhook URL",
                  <code key="w" className="rounded bg-white px-2 py-0.5 font-mono text-xs text-ink-900 border border-ink-200">
                    {acc.webhook_url}
                  </code>,
                ],
                [
                  "Verify token",
                  acc.verify_token_configured ? (
                    <span className="flex items-center gap-1 text-emerald-700">
                      <CheckCircle2 className="h-3.5 w-3.5" /> Configured on server
                    </span>
                  ) : (
                    <span className="text-amber-700">Not configured (WHATSAPP_VERIFY_TOKEN)</span>
                  ),
                ],
                ["Last verified", fmtDateTime(acc.last_verified_at)],
                ["Last error", acc.last_error ?? "—"],
              ]}
            />
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
            <p className="flex items-center gap-1.5 text-xs text-ink-500">
              <KeyRound className="h-3.5 w-3.5 text-ink-400" />
              Tokens are encrypted at rest with AES-256-GCM and never returned to the browser.
            </p>
            <div className="flex gap-2">
              <Button variant="secondary" loading={verify.isPending} onClick={() => verify.mutate()}>
                <RefreshCw className="h-4 w-4" />
                Test connection
              </Button>
              <Button loading={save.isPending} onClick={() => save.mutate()}>
                <Save className="h-4 w-4" />
                Save
              </Button>
            </div>
          </div>
        </div>
      </Card>

      {/* Message Templates Card */}
      <Card
        title={
          <span className="flex items-center gap-2">
            <FileCheck2 className="h-4 w-4 text-brand-700" />
            Meta Message Templates
          </span>
        }
        actions={
          acc.provider === "meta" && (
            <Button size="sm" variant="secondary" loading={sync.isPending} onClick={() => sync.mutate()}>
              <RefreshCw className="h-3.5 w-3.5" />
              Sync status from Meta
            </Button>
          )
        }
        padded={false}
      >
        <div className="border-b border-ink-100 bg-brand-50/40 px-4 py-3">
          <p className="text-xs leading-relaxed text-ink-600">
            Business-initiated messages require Meta-approved templates. ProDesk never assumes approval: only templates
            marked <strong className="font-semibold text-emerald-800">Approved</strong> are sent; others fail safely
            and staff are notified in the inbox.
          </p>
        </div>

        <ul className="divide-y divide-ink-100">
          {templates.map((t) => (
            <li key={t.id} className="grid grid-cols-1 gap-3 p-4 transition-colors hover:bg-ink-50/40 md:grid-cols-[1fr_220px_160px] md:items-center">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs font-semibold text-ink-950">{humanize(t.key)}</span>
                  <span className="rounded bg-ink-100 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider text-ink-600">
                    {humanize(t.category)}
                  </span>
                </div>
                <p className="mt-1 font-mono text-xs text-ink-600 line-clamp-2">{t.body_preview}</p>
                {t.last_error && <p className="mt-1 text-xs text-rose-600">{t.last_error}</p>}
              </div>

              <div>
                <input
                  aria-label={`Template name for ${t.key}`}
                  defaultValue={t.name}
                  onBlur={(e) => e.target.value !== t.name && updTpl.mutate({ id: t.id, b: { name: e.target.value } })}
                  className="h-9 w-full rounded-lg border border-ink-200 bg-white px-3 font-mono text-xs text-ink-900 shadow-xs focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                />
              </div>

              <div>
                <Select
                  aria-label={`Status for ${t.key}`}
                  value={t.status}
                  options={["NOT_SUBMITTED", "PENDING", "APPROVED", "REJECTED", "PAUSED", "DISABLED"]}
                  onChange={(e) => updTpl.mutate({ id: t.id, b: { status: e.target.value } })}
                />
              </div>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}

export function SettingsPage() {
  const [tab, setTab] = useState("firm");
  const { data: org, error } = useQuery({ queryKey: ["org"], queryFn: orgApi.current });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Settings"
        subtitle="Manage firm identity, business hours, WhatsApp automation, and billing configurations."
      />

      <Tabs
        value={tab}
        onChange={setTab}
        tabs={[
          { value: "firm", label: "Firm Profile & Invoicing" },
          { value: "whatsapp", label: "WhatsApp Cloud API" },
        ]}
      />

      <div>
        {error && <ErrorBox error={error} />}
        {tab === "firm" && (org ? <FirmSettings org={org} /> : <Spinner />)}
        {tab === "whatsapp" && <WhatsAppSettings />}
      </div>
    </div>
  );
}

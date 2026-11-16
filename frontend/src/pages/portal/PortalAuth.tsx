import { useMutation, useQuery } from "@tanstack/react-query";
import { Download, MessageSquare, ShieldCheck } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { Button, ErrorBox, Input, Spinner } from "../../components/ui";
import { usePortal } from "../../hooks/usePortal";
import { AuthShell } from "../../layouts/PortalLayout";
import { errorMessage } from "../../services/api";
import { portalApi } from "../../services/endpoints";

/** Phone + OTP. A phone number alone never grants access to anything. */
export function OtpLogin({
  slug: fixedSlug,
  phoneHint,
  onDone,
}: {
  slug?: string;
  phoneHint?: string;
  onDone: () => void;
}) {
  const { verify, loginDemo } = usePortal();
  const [slug, setSlug] = useState(fixedSlug ?? "");
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [sent, setSent] = useState<{ message: string; dev_otp: string | null } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const requestOtp = async (e: FormEvent) => {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      setSent(await portalApi.requestOtp(slug, phone));
    } catch (x) {
      const msg = errorMessage(x);
      if (
        msg.includes("Failed to fetch") ||
        msg.includes("NetworkError") ||
        msg.includes("Load failed") ||
        msg.includes("Network request failed")
      ) {
        setSent({
          message: "Demo mode: verification code dispatched to WhatsApp",
          dev_otp: "123456",
        });
      } else {
        setErr(msg);
      }
    } finally {
      setBusy(false);
    }
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      await verify(slug, phone, code);
      onDone();
    } catch (x) {
      const msg = errorMessage(x);
      if (
        msg.includes("Failed to fetch") ||
        msg.includes("NetworkError") ||
        msg.includes("Load failed") ||
        msg.includes("Network request failed")
      ) {
        loginDemo();
        onDone();
      } else {
        setErr(msg);
      }
    } finally {
      setBusy(false);
    }
  };

  return !sent ? (
    <form onSubmit={requestOtp} className="space-y-4">
      {err && <ErrorBox error={new Error(err)} />}

      {!fixedSlug && (
        <Input
          label="Firm code"
          required
          placeholder="e.g. sharma"
          value={slug}
          onChange={(e) => setSlug(e.target.value.trim().toLowerCase())}
          hint="Shared by your CA firm"
        />
      )}

      <Input
        label="Mobile number"
        required
        inputMode="tel"
        placeholder={phoneHint ?? "98765 43210"}
        value={phone}
        onChange={(e) => setPhone(e.target.value)}
        hint={phoneHint ? `Use the number ending ${phoneHint.slice(-4)}` : undefined}
      />

      <Button type="submit" className="w-full" loading={busy}>
        <MessageSquare className="h-4 w-4" />
        Send code on WhatsApp
      </Button>
    </form>
  ) : (
    <form onSubmit={submit} className="space-y-4">
      {err && <ErrorBox error={new Error(err)} />}

      <div className="rounded-xl border border-emerald-200/80 bg-emerald-50/60 p-3.5 text-xs text-emerald-950">
        <p className="font-medium text-emerald-900">{sent.message}</p>
        <p className="mt-0.5 text-emerald-700">Check your WhatsApp for the 6-digit verification code.</p>
      </div>

      {sent.dev_otp && (
        <div className="rounded-xl border border-amber-200/80 bg-amber-50/70 p-3 text-xs text-amber-900">
          Development mode — your code is{" "}
          <b className="font-mono text-sm tracking-wider text-amber-950" data-testid="dev-otp">
            {sent.dev_otp}
          </b>
        </div>
      )}

      <Input
        label="6-digit code"
        required
        inputMode="numeric"
        maxLength={6}
        autoComplete="one-time-code"
        placeholder="123456"
        value={code}
        onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
      />

      <Button type="submit" className="w-full" loading={busy}>
        <ShieldCheck className="h-4 w-4" />
        Verify & continue
      </Button>

      <div className="text-center pt-1">
        <button
          type="button"
          className="text-xs font-medium text-brand-700 hover:text-brand-800 hover:underline transition-colors"
          onClick={() => setSent(null)}
        >
          Use a different number
        </button>
      </div>
    </form>
  );
}

export function PortalLoginPage() {
  const nav = useNavigate();
  const [params] = useSearchParams();
  const { loginDemo } = usePortal();

  return (
    <AuthShell
      title="Client portal"
      subtitle="Access your tax documents, requests, and invoices securely without remembering passwords."
    >
      {/* Quick Demo Bypass Card */}
      <div className="mb-5 rounded-xl border border-emerald-200/90 bg-emerald-50/60 p-3.5 shadow-xs">
        <div className="flex items-center justify-between">
          <span className="flex items-center gap-1.5 text-xs font-semibold text-emerald-900">
            <span className="flex h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
            Client Demo Access
          </span>
          <span className="text-[10px] uppercase font-bold tracking-wider rounded bg-emerald-200/70 text-emerald-900 px-1.5 py-0.5">
            Bypass Auth
          </span>
        </div>
        <p className="mt-1 text-xs text-emerald-800 leading-relaxed">
          Sign in immediately as demo client <b>Rahul Mehta</b> to view pending documents, tasks, and invoices.
        </p>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={() => {
              loginDemo();
              nav("/portal");
            }}
            className="flex items-center justify-center gap-1.5 rounded-lg bg-emerald-700 px-3 py-2 text-xs font-semibold text-white shadow-xs hover:bg-emerald-800 transition-colors"
          >
            ⚡ Enter Client Portal
          </button>
          <button
            type="button"
            onClick={() => nav("/login")}
            className="flex items-center justify-center gap-1.5 rounded-lg border border-emerald-300 bg-white px-3 py-2 text-xs font-semibold text-emerald-950 shadow-2xs hover:bg-emerald-50 transition-colors"
          >
            ← CA Staff Login
          </button>
        </div>
      </div>

      <OtpLogin slug={params.get("firm") ?? undefined} onDone={() => nav(params.get("next") ?? "/portal")} />
      <div className="mt-5 border-t border-ink-100 pt-4 text-center text-xs text-ink-500">
        Firm staff?{" "}
        <Link className="font-medium text-brand-700 hover:underline" to="/login">
          Sign in here
        </Link>
      </div>
    </AuthShell>
  );
}

/** Opened from the WhatsApp "document ready" notification. */
export function PortalLinkPage() {
  const { token = "" } = useParams();
  const { authenticated } = usePortal();
  const [authed, setAuthed] = useState(authenticated);
  const info = useQuery({ queryKey: ["link", token], queryFn: () => portalApi.linkInfo(token), retry: false });
  const dl = useMutation({
    mutationFn: () => portalApi.linkDownload(token),
    onSuccess: (r) => {
      window.location.assign(r.url);
    },
  });

  if (info.isLoading) {
    return (
      <AuthShell title="Opening secure link">
        <div className="py-6 flex justify-center">
          <Spinner />
        </div>
      </AuthShell>
    );
  }

  if (info.error) {
    return (
      <AuthShell title="Link unavailable">
        <ErrorBox error={new Error(errorMessage(info.error))} />
      </AuthShell>
    );
  }

  const i = info.data!;
  return (
    <AuthShell
      title={`Document from ${i.organization_name}`}
      subtitle="For your security, verify it's you before downloading."
    >
      {!authed ? (
        <OtpLogin slug={i.org_slug} phoneHint={i.phone_hint} onDone={() => setAuthed(true)} />
      ) : (
        <div className="space-y-4">
          <div className="rounded-xl border border-emerald-200/80 bg-emerald-50/60 p-3.5 text-xs text-emerald-900">
            <p className="flex items-center gap-2 font-medium text-emerald-950">
              <ShieldCheck className="h-4 w-4 text-emerald-600" />
              Verified. Your download link is valid for a few minutes.
            </p>
          </div>

          {dl.error && <ErrorBox error={new Error(errorMessage(dl.error))} />}

          <Button className="w-full" loading={dl.isPending} onClick={() => dl.mutate()}>
            <Download className="h-4 w-4" />
            Download document
          </Button>

          <Link
            to="/portal/documents"
            className="block text-center text-xs font-medium text-brand-700 hover:underline"
          >
            Go to all my documents
          </Link>
        </div>
      )}
    </AuthShell>
  );
}

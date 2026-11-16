import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { Button, ErrorBox, Input } from "../../components/ui";
import { useAuth } from "../../hooks/useAuth";
import { AuthShell } from "../../layouts/PortalLayout";
import { errorMessage } from "../../services/api";
import { authApi } from "../../services/endpoints";

export function LoginPage() {
  const { login, loginDemo, me } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (me) return <Navigate to="/" replace />;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      await login(email, password);
      nav("/");
    } catch (x) {
      const msg = errorMessage(x);
      // In live demo without running backend, automatically enter demo mode on network failure
      if (
        msg.includes("Failed to fetch") ||
        msg.includes("NetworkError") ||
        msg.includes("Load failed") ||
        msg.includes("Network request failed")
      ) {
        loginDemo();
        nav("/");
      } else {
        setErr(msg);
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthShell
      title="Sign in to your firm"
      subtitle="Partners, managers and staff — enter your workspace credentials."
    >
      {/* Quick Demo Bypass Card */}
      <div className="mb-5 rounded-xl border border-brand-200/90 bg-brand-50/60 p-3.5 shadow-xs">
        <div className="flex items-center justify-between">
          <span className="flex items-center gap-1.5 text-xs font-semibold text-brand-900">
            <span className="flex h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
            Live Demo Mode
          </span>
          <span className="text-[10px] uppercase font-bold tracking-wider rounded bg-brand-200/70 text-brand-900 px-1.5 py-0.5">
            Bypass Auth
          </span>
        </div>
        <p className="mt-1 text-xs text-brand-800 leading-relaxed">
          Explore the full CA practice workspace with pre-populated clients, filings, and invoices.
        </p>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={() => {
              loginDemo("FIRM_ADMIN");
              nav("/");
            }}
            className="flex items-center justify-center gap-1.5 rounded-lg bg-brand-700 px-3 py-2 text-xs font-semibold text-white shadow-xs hover:bg-brand-800 transition-colors"
          >
            ⚡ CA Admin Demo
          </button>
          <button
            type="button"
            onClick={() => {
              nav("/portal/login?demo=1");
            }}
            className="flex items-center justify-center gap-1.5 rounded-lg border border-brand-300 bg-white px-3 py-2 text-xs font-semibold text-brand-900 shadow-2xs hover:bg-brand-50 transition-colors"
          >
            Client Portal Demo →
          </button>
        </div>
      </div>

      <form onSubmit={submit} className="space-y-4">
        {err && <ErrorBox error={new Error(err)} />}
        <Input
          label="Email"
          type="email"
          autoComplete="username"
          required
          placeholder="ca@yourfirm.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <Input
          label="Password"
          type="password"
          autoComplete="current-password"
          required
          placeholder="••••••••••••"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <Button type="submit" className="w-full" loading={busy}>
          Sign in
        </Button>
      </form>

      <div className="mt-5 flex items-center justify-between text-xs">
        <Link to="/forgot-password" className="text-ink-600 hover:text-brand-700 hover:underline">
          Forgot password?
        </Link>
        <Link to="/register" className="font-medium text-brand-700 hover:underline">
          Register your firm
        </Link>
      </div>

      <div className="mt-5 border-t border-ink-100 pt-4 text-center text-xs text-ink-500">
        Are you a client?{" "}
        <Link to="/portal/login" className="font-semibold text-brand-700 hover:underline">
          Open the client portal
        </Link>
      </div>
    </AuthShell>
  );
}

export function RegisterPage() {
  const { register } = useAuth();
  const nav = useNavigate();
  const [f, setF] = useState({ firm_name: "", admin_name: "", email: "", password: "" });
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      await register(f);
      nav("/onboarding");
    } catch (x) {
      setErr(errorMessage(x));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthShell
      title="Create your ProDesk account"
      subtitle="Set up your practice workspace in under two minutes."
    >
      <form onSubmit={submit} className="space-y-4">
        {err && <ErrorBox error={new Error(err)} />}
        <Input
          label="Firm name"
          required
          placeholder="e.g. Sharma & Associates CA"
          value={f.firm_name}
          onChange={(e) => setF({ ...f, firm_name: e.target.value })}
        />
        <Input
          label="Your name"
          required
          placeholder="e.g. Rajesh Sharma, FCA"
          value={f.admin_name}
          onChange={(e) => setF({ ...f, admin_name: e.target.value })}
        />
        <Input
          label="Work email"
          type="email"
          required
          placeholder="admin@sharma-ca.com"
          value={f.email}
          onChange={(e) => setF({ ...f, email: e.target.value })}
        />
        <Input
          label="Password"
          type="password"
          required
          minLength={10}
          placeholder="••••••••••••"
          hint="At least 10 characters, with letters and numbers"
          value={f.password}
          onChange={(e) => setF({ ...f, password: e.target.value })}
        />
        <Button type="submit" className="w-full" loading={busy}>
          Create account
        </Button>
      </form>

      <p className="mt-5 text-center text-xs text-ink-500">
        Already registered?{" "}
        <Link to="/login" className="font-semibold text-brand-700 hover:underline">
          Sign in
        </Link>
      </p>
    </AuthShell>
  );
}

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  return (
    <AuthShell
      title="Reset your password"
      subtitle="We'll send a secure password reset link to your registered email."
    >
      {done ? (
        <div className="space-y-4">
          <div className="rounded-xl border border-emerald-200/80 bg-emerald-50/60 p-4 text-xs text-emerald-950">
            <p className="font-semibold text-emerald-900">Check your inbox</p>
            <p className="mt-1 text-emerald-700">
              If an account exists for <b className="font-medium text-emerald-950">{email}</b>, a reset link is on its way. The link is valid for 30 minutes.
            </p>
          </div>
          <Link
            to="/login"
            className="block text-center text-xs font-semibold text-brand-700 hover:underline"
          >
            Back to sign in
          </Link>
        </div>
      ) : (
        <form
          className="space-y-4"
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            await authApi.requestReset(email).catch(() => null);
            setBusy(false);
            setDone(true);
          }}
        >
          <Input
            label="Email"
            type="email"
            required
            placeholder="ca@yourfirm.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <Button type="submit" className="w-full" loading={busy}>
            Send reset link
          </Button>
          <div className="text-center pt-2">
            <Link to="/login" className="text-xs text-ink-500 hover:text-brand-700 hover:underline">
              Back to sign in
            </Link>
          </div>
        </form>
      )}
    </AuthShell>
  );
}

export function ResetPasswordPage() {
  const [params] = useSearchParams();
  const nav = useNavigate();
  const [pw, setPw] = useState("");
  const [err, setErr] = useState<string | null>(null);

  return (
    <AuthShell
      title="Choose a new password"
      subtitle="Ensure your password contains at least 10 characters."
    >
      <form
        className="space-y-4"
        onSubmit={async (e) => {
          e.preventDefault();
          try {
            await authApi.confirmReset(params.get("token") ?? "", pw);
            nav("/login");
          } catch (x) {
            setErr(errorMessage(x));
          }
        }}
      >
        {err && <ErrorBox error={new Error(err)} />}
        <Input
          label="New password"
          type="password"
          minLength={10}
          required
          placeholder="••••••••••••"
          value={pw}
          onChange={(e) => setPw(e.target.value)}
        />
        <Button type="submit" className="w-full">
          Update password
        </Button>
      </form>
    </AuthShell>
  );
}

export function ActivatePage() {
  const [params] = useSearchParams();
  const nav = useNavigate();
  const verifyOnly = params.get("verify") === "1";
  const [pw, setPw] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const token = params.get("token") ?? "";

  if (verifyOnly) {
    return (
      <AuthShell title="Verify your email" subtitle="Confirm your email address to activate your account.">
        {msg ? (
          <div className="rounded-xl border border-emerald-200/80 bg-emerald-50/60 p-4 text-xs font-medium text-emerald-900 text-center">
            {msg}
          </div>
        ) : (
          <Button
            className="w-full"
            onClick={async () => {
              try {
                await authApi.verifyEmail(token);
                setMsg("Email verified. You can close this tab.");
              } catch (x) {
                setErr(errorMessage(x));
              }
            }}
          >
            Verify email
          </Button>
        )}
        {err && (
          <div className="mt-3">
            <ErrorBox error={new Error(err)} />
          </div>
        )}
      </AuthShell>
    );
  }

  return (
    <AuthShell
      title="Activate your account"
      subtitle="Set a secure password to join your firm on ProDesk."
    >
      <form
        className="space-y-4"
        onSubmit={async (e) => {
          e.preventDefault();
          try {
            await authApi.activate(token, pw);
            nav("/login");
          } catch (x) {
            setErr(errorMessage(x));
          }
        }}
      >
        {err && <ErrorBox error={new Error(err)} />}
        <Input
          label="Password"
          type="password"
          minLength={10}
          required
          placeholder="••••••••••••"
          value={pw}
          onChange={(e) => setPw(e.target.value)}
        />
        <Button type="submit" className="w-full">
          Activate account
        </Button>
      </form>
    </AuthShell>
  );
}

import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import { tokens } from "../services/api";
import { portalApi } from "../services/endpoints";

interface PortalState {
  authenticated: boolean;
  clientName: string | null;
  firmName: string | null;
  loginDemo: () => void;
  verify: (slug: string, phone: string, code: string) => Promise<void>;
  logout: () => void;
}

const Ctx = createContext<PortalState | null>(null);
const META = "prodesk.portal.meta";

export function PortalProvider({ children }: { children: ReactNode }) {
  const stored = sessionStorage.getItem(META);
  const [meta, setMeta] = useState<{ clientName: string; firmName: string } | null>(stored ? JSON.parse(stored) : null);
  const [authed, setAuthed] = useState<boolean>(
    !!tokens.getPortal() || sessionStorage.getItem("prodesk.demo") === "portal"
  );

  const value = useMemo<PortalState>(() => ({
    authenticated: authed,
    clientName: meta?.clientName ?? (authed ? "Rahul Mehta" : null),
    firmName: meta?.firmName ?? (authed ? "Sharma & Associates (Demo)" : null),
    loginDemo() {
      tokens.setPortal("demo-token-portal");
      sessionStorage.setItem("prodesk.demo", "portal");
      const m = { clientName: "Rahul Mehta", firmName: "Sharma & Associates (Demo)" };
      sessionStorage.setItem(META, JSON.stringify(m));
      setMeta(m);
      setAuthed(true);
    },
    async verify(slug, phone, code) {
      const s = await portalApi.verifyOtp(slug, phone, code);
      tokens.setPortal(s.access_token);
      const m = { clientName: s.client_name, firmName: s.organization_name };
      sessionStorage.setItem(META, JSON.stringify(m));
      setMeta(m);
      setAuthed(true);
    },
    logout() {
      tokens.setPortal(null);
      sessionStorage.removeItem(META);
      sessionStorage.removeItem("prodesk.demo");
      setMeta(null);
      setAuthed(false);
    },
  }), [authed, meta]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function usePortal(): PortalState {
  const v = useContext(Ctx);
  if (!v) throw new Error("usePortal must be used inside PortalProvider");
  return v;
}

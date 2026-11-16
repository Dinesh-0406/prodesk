import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { refreshStaffToken, tokens } from "../services/api";
import { DEMO_ADMIN } from "../services/demoStore";
import { authApi } from "../services/endpoints";
import type { Me } from "../types";

interface AuthState {
  me: Me | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  loginDemo: (role?: "FIRM_ADMIN" | "EMPLOYEE") => void;
  register: (b: { firm_name: string; admin_name: string; email: string; password: string }) => Promise<void>;
  logout: () => Promise<void>;
  can: (perm: string) => boolean;
  reload: () => Promise<void>;
}

const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  const loadMe = useCallback(async () => {
    try {
      setMe(await authApi.me());
    } catch {
      setMe(null);
      tokens.setStaff(null);
    }
  }, []);

  useEffect(() => {
    tokens.onAuthLost(() => setMe(null));
    (async () => {
      // Check for demo mode session
      if (sessionStorage.getItem("prodesk.demo") === "staff" || tokens.getStaff()?.startsWith("demo-")) {
        tokens.setStaff("demo-token-admin");
        setMe(DEMO_ADMIN);
        setLoading(false);
        return;
      }
      if (!tokens.getStaff()) await refreshStaffToken();
      if (tokens.getStaff()) await loadMe();
      setLoading(false);
    })();
  }, [loadMe]);

  const value = useMemo<AuthState>(() => ({
    me,
    loading,
    async login(email, password) {
      const r = await authApi.login(email, password);
      tokens.setStaff(r.access_token);
      await loadMe();
    },
    loginDemo(role = "FIRM_ADMIN") {
      tokens.setStaff("demo-token-admin");
      sessionStorage.setItem("prodesk.demo", "staff");
      if (role === "FIRM_ADMIN") {
        setMe(DEMO_ADMIN);
      } else {
        setMe({
          ...DEMO_ADMIN,
          id: "u-emp1",
          full_name: "Vikram Joshi",
          role: "EMPLOYEE",
          permissions: ["CLIENT_VIEW", "DOCUMENT_VIEW", "TASK_VIEW", "WHATSAPP_VIEW"],
        });
      }
      setLoading(false);
    },
    async register(b) {
      const r = await authApi.register(b);
      tokens.setStaff(r.access_token);
      await loadMe();
    },
    async logout() {
      try {
        if (!sessionStorage.getItem("prodesk.demo")) {
          await authApi.logout();
        }
      } finally {
        tokens.setStaff(null);
        sessionStorage.removeItem("prodesk.demo");
        setMe(null);
      }
    },
    can: (perm: string) => !!me?.permissions.includes(perm),
    reload: loadMe,
  }), [me, loading, loadMe]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAuth must be used inside AuthProvider");
  return v;
}

/** Renders children only when the user has the permission (UI hint; the API enforces it). */
export function Can({ perm, children, fallback = null }: { perm: string; children: ReactNode; fallback?: ReactNode }) {
  const { can } = useAuth();
  return <>{can(perm) ? children : fallback}</>;
}

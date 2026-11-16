import { CheckCircle2, XCircle } from "lucide-react";
import { createContext, useCallback, useContext, useState, type ReactNode } from "react";
import { cn } from "../utils/format";

interface Toast { id: number; kind: "success" | "error"; text: string }
const Ctx = createContext<(kind: Toast["kind"], text: string) => void>(() => undefined);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const push = useCallback((kind: Toast["kind"], text: string) => {
    const id = Date.now() + Math.random();
    setItems((x) => [...x, { id, kind, text }]);
    setTimeout(() => setItems((x) => x.filter((t) => t.id !== id)), 4500);
  }, []);
  return (
    <Ctx.Provider value={push}>
      {children}
      <div className="pointer-events-none fixed bottom-4 right-4 z-[60] flex w-80 flex-col gap-2" aria-live="polite">
        {items.map((t) => (
          <div key={t.id} role="status"
            className={cn("pointer-events-auto flex items-start gap-2 rounded-lg border bg-white px-3 py-2.5 text-sm shadow-lg",
              t.kind === "success" ? "border-brand-200" : "border-red-200")}>
            {t.kind === "success" ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-brand-600" /> : <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-600" />}
            <span className="text-ink-800">{t.text}</span>
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
}

export const useToast = () => useContext(Ctx);

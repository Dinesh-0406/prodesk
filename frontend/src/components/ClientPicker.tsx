import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { useState } from "react";
import { useDebounce } from "../hooks/useDebounce";
import { clientApi } from "../services/endpoints";
import type { Client } from "../types";
import { Field } from "./ui";

/** Searchable client selector (server-side search, tenant-scoped by the API). */
export function ClientPicker({
  value,
  onChange,
  label = "Client",
}: {
  value: string;
  onChange: (id: string, c?: Client) => void;
  label?: string;
}) {
  const [q, setQ] = useState("");
  const dq = useDebounce(q, 250);
  const { data } = useQuery({
    queryKey: ["clients", "picker", dq],
    queryFn: () => clientApi.list({ q: dq, page_size: 20 }),
  });

  return (
    <Field label={label}>
      <div className="space-y-2">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-ink-400" />
          <input
            aria-label="Search clients"
            placeholder="Search by client name, mobile, PAN…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="block w-full rounded-lg border border-ink-200 bg-ink-50/50 pl-8 pr-3 py-1.5 text-xs text-ink-900 placeholder:text-ink-400 focus:border-brand-600 focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/15 transition-all shadow-2xs"
          />
        </div>
        <select
          aria-label={label}
          required
          value={value}
          onChange={(e) => onChange(e.target.value, data?.items.find((c) => c.id === e.target.value))}
          className="block w-full rounded-lg border border-ink-200 bg-white px-3 py-2 text-xs font-medium text-ink-900 focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-500/15 transition-all shadow-2xs"
        >
          <option value="">Select a client from practice…</option>
          {data?.items.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name} · {c.phone} {c.pan ? `(${c.pan})` : ""}
            </option>
          ))}
        </select>
      </div>
    </Field>
  );
}

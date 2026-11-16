import { useMutation } from "@tanstack/react-query";
import {
  ArrowRight,
  Bot,
  CheckCircle2,
  Send,
  Sparkles,
} from "lucide-react";
import { useState } from "react";
import { Button, Card, ErrorBox, PageHeader } from "../components/ui";
import { errorMessage } from "../services/api";
import { insightApi } from "../services/endpoints";
import type { AIAnswer } from "../types";
import { humanize } from "../utils/format";

const PROMPT_CATEGORIES = [
  {
    category: "Compliance & Deadlines",
    prompts: [
      "Which clients have pending documents?",
      "Show overdue ITR tasks.",
      "Which tasks are due this week?",
    ],
  },
  {
    category: "Billing & Collections",
    prompts: [
      "Which invoices are unpaid?",
      "List clients with highest outstanding balances.",
    ],
  },
  {
    category: "Team & Workload",
    prompts: [
      "Which clients are assigned to Vikram?",
      "Which clients haven't submitted bank statements?",
    ],
  },
];

export function AssistantPage() {
  const [q, setQ] = useState("");
  const [history, setHistory] = useState<{ q: string; a: AIAnswer }[]>([]);

  const ask = useMutation({
    mutationFn: (question: string) => insightApi.ask(question),
    onSuccess: (a, question) => {
      setHistory((h) => [{ q: question, a }, ...h]);
      setQ("");
    },
  });

  const handleAsk = (queryText: string) => {
    const trimmed = queryText.trim();
    if (!trimmed || ask.isPending) return;
    ask.mutate(trimmed);
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="AI Assistant"
        subtitle="Ask natural language questions about your clients, filings, invoices, and deadlines. Answers are strictly grounded in your firm's live database."
      />

      {/* Modern Search/Prompt Console */}
      <Card>
        <div className="space-y-4">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleAsk(q);
            }}
            className="relative"
          >
            <div className="relative flex items-center">
              <Sparkles className="pointer-events-none absolute left-3.5 h-5 w-5 text-brand-600" />
              <input
                aria-label="Ask the assistant"
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Ask anything... e.g. Which clients have pending documents?"
                className="h-12 w-full rounded-xl border border-ink-200/90 bg-ink-50/50 pl-11 pr-24 text-sm text-ink-900 placeholder:text-ink-400 shadow-inner focus:border-brand-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 transition-all"
              />
              <div className="absolute right-2 flex items-center gap-1.5">
                <Button type="submit" size="sm" loading={ask.isPending} disabled={!q.trim()}>
                  <Send className="h-3.5 w-3.5" />
                  Ask
                </Button>
              </div>
            </div>
          </form>

          {ask.error && <ErrorBox error={new Error(errorMessage(ask.error))} />}

          {/* Quick Prompt Suggestions */}
          <div className="space-y-2 pt-1">
            <p className="text-xs font-semibold uppercase tracking-wider text-ink-400">Suggested Inquiries</p>
            <div className="flex flex-wrap gap-2">
              {PROMPT_CATEGORIES.flatMap((c) => c.prompts).map((item) => (
                <button
                  key={item}
                  type="button"
                  onClick={() => {
                    setQ(item);
                    handleAsk(item);
                  }}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-ink-200/80 bg-white px-3 py-1.5 text-xs text-ink-700 shadow-xs hover:border-brand-300 hover:bg-brand-50/40 hover:text-brand-800 transition-all"
                >
                  <span>{item}</span>
                  <ArrowRight className="h-3 w-3 text-ink-400" />
                </button>
              ))}
            </div>
          </div>
        </div>
      </Card>

      {/* Answer Stream */}
      <div className="space-y-5">
        {history.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-ink-200 p-8 text-center bg-white/50">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-50 text-brand-700 mb-3">
              <Bot className="h-6 w-6" />
            </div>
            <h3 className="text-sm font-semibold text-ink-900">Your Intelligent Practice Copilot</h3>
            <p className="mx-auto mt-1 max-w-md text-xs leading-relaxed text-ink-500">
              Query your data without building complex reports. Ask about pending client documents, overdue GST filings,
              outstanding invoices, or team task allocations.
            </p>
          </div>
        ) : (
          history.map(({ q: question, a }, i) => (
            <Card
              key={i}
              title={
                <div className="flex items-center gap-2">
                  <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand-50 text-brand-700">
                    <Bot className="h-4 w-4" />
                  </div>
                  <span className="text-sm font-semibold text-ink-950">{question}</span>
                </div>
              }
              padded={false}
            >
              {/* Answer summary */}
              <div className="border-b border-ink-100 bg-brand-50/20 px-5 py-3.5">
                <p className="text-sm font-medium leading-relaxed text-ink-900">{a.answer}</p>
              </div>

              {/* Tabular data rows if present */}
              {a.rows.length > 0 && (
                <div className="overflow-x-auto">
                  <table className="min-w-full text-sm">
                    <thead>
                      <tr className="border-b border-ink-200/80 bg-ink-50/60 text-left text-[11px] font-semibold uppercase tracking-wider text-ink-500">
                        {a.columns.map((c) => (
                          <th key={c} className="px-5 py-2.5">
                            {humanize(c)}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-ink-100">
                      {a.rows.map((r, j) => (
                        <tr key={j} className="hover:bg-ink-50/40 transition-colors">
                          {a.columns.map((c) => (
                            <td key={c} className="px-5 py-2.5 text-xs text-ink-700 font-mono">
                              {String(r[c] ?? "—")}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Grounding & Disclaimer Footer */}
              <div className="flex items-center justify-between px-5 py-2.5 bg-ink-50/40 text-[11px] text-ink-500">
                <span className="flex items-center gap-1.5">
                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                  Grounded in practice records
                </span>
                <span>{a.disclaimer}</span>
              </div>
            </Card>
          ))
        )}
      </div>
    </div>
  );
}

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, Hand, RotateCcw, Send, UserCheck } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Avatar, Badge, Button, Spinner } from "../../components/ui";
import { Can } from "../../hooks/useAuth";
import { useToast } from "../../hooks/useToast";
import { errorMessage } from "../../services/api";
import { whatsappApi } from "../../services/endpoints";
import type { Conversation } from "../../types";
import { cn, fmtDateTime, humanize } from "../../utils/format";

export function MessageThread({ conv }: { conv: Conversation }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [text, setText] = useState("");
  const end = useRef<HTMLDivElement>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["messages", conv.id],
    queryFn: () => whatsappApi.messages(conv.id),
    refetchInterval: 5000,
  });

  useEffect(() => {
    end.current?.scrollIntoView?.({ block: "end" });
  }, [data?.items.length]);

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["messages", conv.id] });
    qc.invalidateQueries({ queryKey: ["conversations"] });
  };

  const send = useMutation({
    mutationFn: () => whatsappApi.reply(conv.id, text),
    onSuccess: () => {
      setText("");
      refresh();
    },
    onError: (e) => toast("error", errorMessage(e)),
  });

  const handover = useMutation({
    mutationFn: (action: string) => whatsappApi.handover(conv.id, action),
    onSuccess: refresh,
    onError: (e) => toast("error", errorMessage(e)),
  });

  const human = ["HUMAN_REQUESTED", "AGENT_ASSIGNED", "HUMAN_ACTIVE"].includes(conv.handover_state);
  const clientTitle = conv.client
    ? conv.client.name
    : conv.contact.profile_name ?? `+${conv.contact.wa_id}`;

  return (
    <div className="flex h-full flex-col bg-white">
      {/* Thread Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-ink-100/90 px-5 py-3.5 bg-white">
        <div className="flex items-center gap-3 min-w-0">
          <Avatar name={clientTitle} size="md" />
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="font-semibold text-xs text-ink-950 truncate">
                {conv.client ? (
                  <Link className="hover:text-brand-700 hover:underline" to={`/clients/${conv.client.id}`}>
                    {conv.client.name}
                  </Link>
                ) : (
                  clientTitle
                )}
              </span>
              <span className="font-mono text-[11px] text-ink-400">+{conv.contact.wa_id}</span>
            </div>
            <p className="text-[11px] text-ink-500 mt-0.5">
              {conv.service_window_open ? (
                <span className="text-emerald-700 font-medium flex items-center gap-1">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  24h customer service window open
                </span>
              ) : (
                <span className="text-amber-700 font-medium">Window closed · pre-approved templates only</span>
              )}
            </p>
          </div>
        </div>

        {/* Handover & Agent Controls */}
        <div className="flex flex-wrap items-center gap-2">
          <Badge
            value={conv.handover_state}
            label={
              {
                HUMAN_REQUESTED: "Waiting for a person",
                AGENT_ASSIGNED: "Agent assigned",
                HUMAN_ACTIVE: "Agent replying",
                BOT: "AI Assistant replying",
                BOT_RESUMED: "AI Assistant replying",
              }[conv.handover_state]
            }
          />
          {conv.assigned_agent && (
            <span className="text-xs text-ink-600 bg-ink-100 px-2 py-0.5 rounded font-medium">
              {conv.assigned_agent.full_name}
            </span>
          )}
          <Can perm="WHATSAPP_SEND">
            {!human && (
              <Button size="xs" variant="secondary" onClick={() => handover.mutate("take")} className="gap-1">
                <Hand className="h-3 w-3" />
                <span>Take over</span>
              </Button>
            )}
            {conv.handover_state === "HUMAN_REQUESTED" && (
              <Button size="xs" onClick={() => handover.mutate("take")} className="gap-1 shadow-xs">
                <UserCheck className="h-3 w-3" />
                <span>Accept</span>
              </Button>
            )}
            {human && (
              <Button
                size="xs"
                variant="outline"
                onClick={() => handover.mutate("resume_bot")}
                className="gap-1"
              >
                <RotateCcw className="h-3 w-3" />
                <span>Hand back to assistant</span>
              </Button>
            )}
          </Can>
        </div>
      </div>

      {/* Messages Canvas */}
      <div className="flex-1 space-y-3 overflow-y-auto bg-ink-50/50 p-5">
        {isLoading && <Spinner label="Loading conversation thread…" />}
        {data?.items.map((m) => {
          const isInbound = m.direction === "INBOUND";
          const isAgent = m.sender === "AGENT";
          const isBot = m.sender === "BOT";

          return (
            <div key={m.id} className={cn("flex", isInbound ? "justify-start" : "justify-end")}>
              <div
                className={cn(
                  "max-w-[75%] rounded-2xl px-4 py-2.5 text-xs shadow-2xs space-y-1 transition-all",
                  isInbound
                    ? "bg-white text-ink-950 border border-ink-200/80 rounded-bl-xs"
                    : isAgent
                    ? "bg-brand-700 text-white border border-brand-800 rounded-br-xs"
                    : "bg-emerald-50 text-emerald-950 border border-emerald-200/80 rounded-br-xs",
                  m.status === "FAILED" && "ring-1 ring-rose-400"
                )}
              >
                {m.template_key && (
                  <p
                    className={cn(
                      "text-[10px] font-bold uppercase tracking-wider",
                      isAgent ? "text-brand-200" : isBot ? "text-emerald-700" : "text-ink-400"
                    )}
                  >
                    Template · {humanize(m.template_key)}
                  </p>
                )}
                <p className="whitespace-pre-wrap break-words leading-relaxed font-normal">
                  {m.body ?? `[${m.message_type.toLowerCase()} attachment]`}
                </p>
                <div
                  className={cn(
                    "flex items-center gap-1.5 text-[10px] pt-0.5",
                    isAgent ? "text-brand-100" : isBot ? "text-emerald-700" : "text-ink-400"
                  )}
                >
                  {isBot && <Bot className="h-3 w-3" />}
                  <span>{humanize(m.sender)}</span>
                  <span>·</span>
                  <span className="tabular-nums">{fmtDateTime(m.timestamp)}</span>
                  {!isInbound && (
                    <>
                      <span>·</span>
                      <span>{humanize(m.status)}</span>
                    </>
                  )}
                </div>
                {m.status === "FAILED" && (
                  <p className="text-[10px] font-medium text-rose-600 bg-rose-50 p-1 rounded">
                    {m.error_code}: {m.error}
                  </p>
                )}
              </div>
            </div>
          );
        })}
        <div ref={end} />
      </div>

      {/* Reply Composer Form */}
      <Can perm="WHATSAPP_SEND">
        <form
          className="flex items-center gap-2 border-t border-ink-100/90 bg-white p-3.5"
          onSubmit={(e) => {
            e.preventDefault();
            if (text.trim()) send.mutate();
          }}
        >
          <input
            aria-label="Reply"
            value={text}
            onChange={(e) => setText(e.target.value)}
            disabled={!conv.service_window_open}
            placeholder={
              conv.service_window_open
                ? "Type a WhatsApp reply… (sending takes over from AI assistant)"
                : "The 24-hour service window is closed; outbound messages require pre-approved templates"
            }
            className="h-10 flex-1 rounded-xl border border-ink-200 bg-ink-50/50 px-3.5 text-xs text-ink-900 placeholder:text-ink-400 focus:border-brand-600 focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/15 disabled:bg-ink-50 disabled:cursor-not-allowed transition-all shadow-2xs"
          />
          <Button
            type="submit"
            loading={send.isPending}
            disabled={!conv.service_window_open || !text.trim()}
            className="gap-1.5 shadow-sm h-10 px-4"
          >
            <Send className="h-3.5 w-3.5" />
            <span>Send</span>
          </Button>
        </form>
      </Can>
    </div>
  );
}

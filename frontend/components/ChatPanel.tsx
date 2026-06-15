"use client";

import { useEffect, useRef, useState } from "react";
import type { ChatResponse, ChatTrade, ChatWatchlistChange } from "@/lib/types";
import { qty } from "@/lib/format";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  trades?: ChatTrade[];
  watchlistChanges?: ChatWatchlistChange[];
}

function tradeLabel(t: ChatTrade): string {
  return `${t.side.toUpperCase()} ${qty(t.quantity)} ${t.ticker}`;
}

function watchLabel(c: ChatWatchlistChange): string {
  return `${c.action === "add" ? "Added" : "Removed"} ${c.ticker}`;
}

/** Collapsible AI chat sidebar with inline trade/watchlist action confirmations. */
export function ChatPanel({
  onSend,
}: {
  onSend: (message: string) => Promise<ChatResponse>;
}) {
  const [open, setOpen] = useState(true);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, loading]);

  const send = async () => {
    const text = input.trim();
    if (!text || loading) return;
    setMessages((m) => [...m, { role: "user", content: text }]);
    setInput("");
    setLoading(true);
    try {
      const res = await onSend(text);
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: res.message,
          trades: res.trades,
          watchlistChanges: res.watchlist_changes,
        },
      ]);
    } catch (e) {
      setMessages((m) => [
        ...m,
        { role: "assistant", content: e instanceof Error ? e.message : "Request failed" },
      ]);
    } finally {
      setLoading(false);
    }
  };

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="rounded border border-border bg-panel px-3 py-2 text-xs font-semibold text-accent"
      >
        Open AI Chat
      </button>
    );
  }

  return (
    <section className="flex h-full w-80 flex-col rounded border border-border bg-panel">
      <div className="flex items-center justify-between border-b border-border px-3 py-2">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-accent">FinAlly AI</h2>
        <button onClick={() => setOpen(false)} className="text-muted hover:text-foreground" aria-label="Collapse chat">
          &minus;
        </button>
      </div>

      <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto px-3 py-3">
        {messages.length === 0 && (
          <p className="text-xs text-muted">
            Ask about your portfolio, request analysis, or have me execute trades.
          </p>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            data-testid="chat-message"
            data-role={m.role}
            className={m.role === "user" ? "text-right" : "text-left"}
          >
            <div
              className={`inline-block max-w-[90%] rounded px-2 py-1.5 text-sm ${
                m.role === "user"
                  ? "bg-blue/20 text-foreground"
                  : "bg-panel-elevated text-foreground"
              }`}
            >
              {m.content}
            </div>
            {(m.trades?.length || m.watchlistChanges?.length) ? (
              <div className="mt-1 space-y-1">
                {m.trades?.map((t, j) => (
                  <div
                    key={`t${j}`}
                    data-testid="chat-action"
                    className="rounded border border-border bg-background px-2 py-1 text-[11px] text-up"
                  >
                    {tradeLabel(t)}
                  </div>
                ))}
                {m.watchlistChanges?.map((c, j) => (
                  <div
                    key={`w${j}`}
                    data-testid="chat-action"
                    className="rounded border border-border bg-background px-2 py-1 text-[11px] text-blue"
                  >
                    {watchLabel(c)}
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        ))}
        {loading && <div className="text-xs text-muted">FinAlly is thinking...</div>}
      </div>

      <div className="flex gap-1 border-t border-border p-2">
        <input
          data-testid="chat-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="Message FinAlly..."
          className="flex-1 rounded border border-border bg-background px-2 py-1.5 text-sm outline-none focus:border-blue"
        />
        <button
          data-testid="chat-send-btn"
          onClick={send}
          disabled={loading}
          className="rounded bg-purple px-3 py-1.5 text-sm font-semibold text-foreground hover:opacity-90 disabled:opacity-50"
        >
          Send
        </button>
      </div>
    </section>
  );
}

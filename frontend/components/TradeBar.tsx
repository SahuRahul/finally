"use client";

import { useState } from "react";

/** Market-order trade bar. Instant fill via parent's onTrade handler. */
export function TradeBar({
  ticker,
  onTrade,
}: {
  ticker: string | null;
  onTrade: (ticker: string, quantity: number, side: "buy" | "sell") => Promise<void>;
}) {
  const [symbol, setSymbol] = useState(ticker ?? "");
  const [quantity, setQuantity] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Mirror the selected ticker into the field when it changes (adjust state
  // during render, the React-recommended alternative to a syncing effect).
  const [lastTicker, setLastTicker] = useState(ticker);
  if (ticker && ticker !== lastTicker) {
    setLastTicker(ticker);
    setSymbol(ticker);
  }

  const submit = async (side: "buy" | "sell") => {
    const t = symbol.trim().toUpperCase();
    const q = Number(quantity);
    if (!t || !Number.isFinite(q) || q <= 0) {
      setError("Enter a ticker and positive quantity");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await onTrade(t, q, side);
      setQuantity("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Trade failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex items-center gap-2 rounded border border-border bg-panel px-3 py-2">
      <input
        data-testid="trade-ticker"
        value={symbol}
        onChange={(e) => setSymbol(e.target.value)}
        placeholder="Ticker"
        className="w-24 rounded border border-border bg-background px-2 py-1.5 text-sm uppercase outline-none focus:border-blue"
      />
      <input
        data-testid="trade-quantity"
        value={quantity}
        onChange={(e) => setQuantity(e.target.value)}
        placeholder="Qty"
        inputMode="decimal"
        className="w-24 rounded border border-border bg-background px-2 py-1.5 text-sm outline-none focus:border-blue"
      />
      <button
        data-testid="trade-buy-btn"
        disabled={busy}
        onClick={() => submit("buy")}
        className="rounded bg-up px-4 py-1.5 text-sm font-semibold text-background hover:opacity-90 disabled:opacity-50"
      >
        Buy
      </button>
      <button
        data-testid="trade-sell-btn"
        disabled={busy}
        onClick={() => submit("sell")}
        className="rounded bg-down px-4 py-1.5 text-sm font-semibold text-background hover:opacity-90 disabled:opacity-50"
      >
        Sell
      </button>
      {error && <span className="text-xs text-down">{error}</span>}
    </div>
  );
}

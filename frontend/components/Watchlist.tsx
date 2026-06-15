"use client";

import { useState } from "react";
import type { PriceMap, WatchlistItem } from "@/lib/types";
import { pct, pnlClass } from "@/lib/format";
import { PriceCell } from "./PriceCell";
import { Sparkline } from "./Sparkline";

/**
 * Merges static watchlist rows with the live price map and per-ticker
 * sparkline history. Clicking a row selects it for the main chart.
 */
export function Watchlist({
  items,
  prices,
  history,
  selected,
  onSelect,
  onAdd,
  onRemove,
}: {
  items: WatchlistItem[];
  prices: PriceMap;
  history: Record<string, number[]>;
  selected: string | null;
  onSelect: (ticker: string) => void;
  onAdd: (ticker: string) => void;
  onRemove: (ticker: string) => void;
}) {
  const [input, setInput] = useState("");

  const submit = () => {
    const t = input.trim().toUpperCase();
    if (t) onAdd(t);
    setInput("");
  };

  return (
    <section
      data-testid="watchlist"
      className="flex h-full flex-col rounded border border-border bg-panel"
    >
      <div className="flex items-center justify-between border-b border-border px-3 py-2">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-muted">Watchlist</h2>
        <div className="flex gap-1">
          <input
            data-testid="watchlist-add-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit()}
            placeholder="Add ticker"
            className="w-24 rounded border border-border bg-background px-2 py-1 text-xs uppercase outline-none focus:border-blue"
          />
          <button
            data-testid="watchlist-add-btn"
            onClick={submit}
            className="rounded bg-blue px-2 py-1 text-xs font-semibold text-background hover:opacity-90"
          >
            Add
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        <table className="w-full text-sm">
          <tbody>
            {items.map((item) => {
              const live = prices[item.ticker];
              const price = live?.price ?? item.price ?? null;
              const changePct = live?.change_percent ?? item.change_percent ?? 0;
              const isSelected = selected === item.ticker;
              return (
                <tr
                  key={item.ticker}
                  data-testid={`watchlist-row-${item.ticker}`}
                  onClick={() => onSelect(item.ticker)}
                  className={`cursor-pointer border-b border-border/50 hover:bg-panel-elevated ${
                    isSelected ? "bg-panel-elevated" : ""
                  }`}
                >
                  <td className="px-3 py-1.5 font-mono font-semibold">{item.ticker}</td>
                  <td className="px-2 py-1.5 text-right">
                    <PriceCell price={price} testId="price" />
                  </td>
                  <td className={`px-2 py-1.5 text-right font-mono text-xs ${pnlClass(changePct)}`}>
                    {pct(changePct)}
                  </td>
                  <td className="px-2 py-1.5">
                    <Sparkline data={history[item.ticker] ?? []} />
                  </td>
                  <td className="px-2 py-1.5 text-right">
                    <button
                      data-testid={`watchlist-remove-${item.ticker}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        onRemove(item.ticker);
                      }}
                      className="text-muted hover:text-down"
                      aria-label={`Remove ${item.ticker}`}
                    >
                      &times;
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

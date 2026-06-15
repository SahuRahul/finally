"use client";

import type { PriceMap, Position } from "@/lib/types";
import { pct, pnlClass, qty, signed, usd } from "@/lib/format";
import { PriceCell } from "./PriceCell";

/**
 * Positions table. Current price prefers the live SSE map, falling back to
 * the value the backend returned with the portfolio.
 */
export function PositionsTable({
  positions,
  prices,
  onSelect,
}: {
  positions: Position[];
  prices: PriceMap;
  onSelect: (ticker: string) => void;
}) {
  return (
    <section className="flex h-full flex-col rounded border border-border bg-panel">
      <div className="border-b border-border px-3 py-2">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-muted">Positions</h2>
      </div>
      <div className="flex-1 overflow-y-auto">
        <table data-testid="positions-table" className="w-full text-sm">
          <thead className="sticky top-0 bg-panel text-[10px] uppercase tracking-wide text-muted">
            <tr>
              <th className="px-3 py-1.5 text-left font-medium">Ticker</th>
              <th className="px-2 py-1.5 text-right font-medium">Qty</th>
              <th className="px-2 py-1.5 text-right font-medium">Avg Cost</th>
              <th className="px-2 py-1.5 text-right font-medium">Price</th>
              <th className="px-2 py-1.5 text-right font-medium">Unrl P&amp;L</th>
              <th className="px-3 py-1.5 text-right font-medium">%</th>
            </tr>
          </thead>
          <tbody>
            {positions.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-3 py-6 text-center text-xs text-muted">
                  No open positions
                </td>
              </tr>
            ) : (
              positions.map((p) => {
                const price = prices[p.ticker]?.price ?? p.current_price;
                return (
                  <tr
                    key={p.ticker}
                    data-testid={`position-row-${p.ticker}`}
                    onClick={() => onSelect(p.ticker)}
                    className="cursor-pointer border-b border-border/50 font-mono hover:bg-panel-elevated"
                  >
                    <td className="px-3 py-1.5 font-semibold">{p.ticker}</td>
                    <td className="px-2 py-1.5 text-right">{qty(p.quantity)}</td>
                    <td className="px-2 py-1.5 text-right">{usd(p.avg_cost)}</td>
                    <td className="px-2 py-1.5 text-right">
                      <PriceCell price={price} />
                    </td>
                    <td className={`px-2 py-1.5 text-right ${pnlClass(p.unrealized_pnl)}`}>
                      {signed(p.unrealized_pnl)}
                    </td>
                    <td className={`px-3 py-1.5 text-right ${pnlClass(p.unrealized_pnl_percent)}`}>
                      {pct(p.unrealized_pnl_percent)}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

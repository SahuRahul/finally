"use client";

import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { usd } from "@/lib/format";

/**
 * Larger price-over-time chart for the selected ticker. Uses the sparkline
 * history accumulated from the SSE stream since page load.
 */
export function PriceChart({
  ticker,
  history,
}: {
  ticker: string | null;
  history: number[];
}) {
  const data = history.map((price, i) => ({ i, price }));

  return (
    <section
      data-testid="price-chart"
      className="flex h-full flex-col rounded border border-border bg-panel"
    >
      <div className="border-b border-border px-3 py-2">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-muted">
          {ticker ? `${ticker} — Price` : "Select a ticker"}
        </h2>
      </div>
      <div className="flex-1 p-2">
        {data.length < 2 ? (
          <div className="flex h-full items-center justify-center text-xs text-muted">
            Accumulating price data...
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 8 }}>
              <defs>
                <linearGradient id="priceFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--blue)" stopOpacity={0.4} />
                  <stop offset="100%" stopColor="var(--blue)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="i" hide />
              <YAxis
                domain={["auto", "auto"]}
                tick={{ fill: "var(--muted)", fontSize: 10 }}
                width={56}
                tickFormatter={(v) => usd(v)}
              />
              <Tooltip
                contentStyle={{
                  background: "var(--panel-elevated)",
                  border: "1px solid var(--border)",
                  borderRadius: 6,
                  fontSize: 12,
                }}
                labelFormatter={() => ""}
                formatter={(v) => [usd(Number(v)), "Price"]}
              />
              <Area
                type="monotone"
                dataKey="price"
                stroke="var(--blue)"
                strokeWidth={2}
                fill="url(#priceFill)"
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </section>
  );
}

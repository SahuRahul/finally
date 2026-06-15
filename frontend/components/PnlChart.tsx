"use client";

import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Snapshot } from "@/lib/types";
import { usd } from "@/lib/format";

/** Total portfolio value over time, from /api/portfolio/history. */
export function PnlChart({ snapshots }: { snapshots: Snapshot[] }) {
  const data = snapshots.map((s) => ({
    t: new Date(s.recorded_at).getTime(),
    value: s.total_value,
  }));

  return (
    <section
      data-testid="pnl-chart"
      className="flex h-full flex-col rounded border border-border bg-panel"
    >
      <div className="border-b border-border px-3 py-2">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-muted">
          Portfolio Value
        </h2>
      </div>
      <div className="flex-1 p-2">
        {data.length < 2 ? (
          <div className="flex h-full items-center justify-center text-xs text-muted">
            No history yet
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 8 }}>
              <XAxis dataKey="t" hide />
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
                labelFormatter={(t) => new Date(Number(t)).toLocaleTimeString()}
                formatter={(v) => [usd(Number(v)), "Value"]}
              />
              <Line
                type="monotone"
                dataKey="value"
                stroke="var(--accent)"
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </section>
  );
}

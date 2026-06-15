"use client";

import { ResponsiveContainer, Treemap } from "recharts";
import type { Position } from "@/lib/types";
import { pct } from "@/lib/format";

/** Color a tile by P&L percent: green for gains, red for losses. */
function pnlColor(pnlPercent: number): string {
  const clamped = Math.max(-5, Math.min(5, pnlPercent)) / 5;
  if (clamped >= 0) {
    const a = 0.25 + clamped * 0.45;
    return `rgba(63, 185, 80, ${a.toFixed(2)})`;
  }
  const a = 0.25 + Math.abs(clamped) * 0.45;
  return `rgba(248, 81, 73, ${a.toFixed(2)})`;
}

interface TileProps {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  ticker?: string;
  pnlPercent?: number;
}

function Tile({ x = 0, y = 0, width = 0, height = 0, ticker, pnlPercent }: TileProps) {
  if (!ticker) return null;
  const showLabel = width > 44 && height > 24;
  return (
    <g>
      <rect
        x={x}
        y={y}
        width={width}
        height={height}
        fill={pnlColor(pnlPercent ?? 0)}
        stroke="var(--background)"
        strokeWidth={2}
      />
      {showLabel && (
        <>
          <text x={x + 6} y={y + 16} fill="var(--foreground)" fontSize={12} fontWeight={600}>
            {ticker}
          </text>
          <text x={x + 6} y={y + 30} fill="var(--foreground)" fontSize={10} opacity={0.85}>
            {pct(pnlPercent ?? 0)}
          </text>
        </>
      )}
    </g>
  );
}

export function Heatmap({ positions }: { positions: Position[] }) {
  const data = positions.map((p) => ({
    name: p.ticker,
    ticker: p.ticker,
    size: p.market_value,
    pnlPercent: p.unrealized_pnl_percent,
  }));

  return (
    <section
      data-testid="portfolio-heatmap"
      className="flex h-full flex-col rounded border border-border bg-panel"
    >
      <div className="border-b border-border px-3 py-2">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-muted">
          Portfolio Heatmap
        </h2>
      </div>
      <div className="flex-1 p-1">
        {data.length === 0 ? (
          <div className="flex h-full items-center justify-center text-xs text-muted">
            No positions
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <Treemap
              data={data}
              dataKey="size"
              nameKey="name"
              content={<Tile />}
              isAnimationActive={false}
            />
          </ResponsiveContainer>
        )}
      </div>
    </section>
  );
}

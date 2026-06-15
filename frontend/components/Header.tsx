"use client";

import type { ConnectionStatus } from "@/lib/types";
import { usd } from "@/lib/format";

const STATUS_META: Record<ConnectionStatus, { color: string; label: string }> = {
  connected: { color: "var(--up)", label: "Connected" },
  reconnecting: { color: "var(--accent)", label: "Reconnecting" },
  disconnected: { color: "var(--down)", label: "Disconnected" },
};

export function Header({
  totalValue,
  cashBalance,
  status,
}: {
  totalValue: number;
  cashBalance: number;
  status: ConnectionStatus;
}) {
  const meta = STATUS_META[status];

  return (
    <header className="flex items-center justify-between border-b border-border bg-panel px-4 py-2">
      <div className="flex items-baseline gap-2">
        <span className="text-lg font-bold tracking-tight text-accent">FinAlly</span>
        <span className="text-xs text-muted">AI Trading Workstation</span>
      </div>

      <div className="flex items-center gap-6 font-mono text-sm">
        <div className="flex flex-col items-end">
          <span className="text-[10px] uppercase tracking-wide text-muted">Total Value</span>
          <span data-testid="total-value" className="font-semibold text-foreground">
            {usd(totalValue)}
          </span>
        </div>
        <div className="flex flex-col items-end">
          <span className="text-[10px] uppercase tracking-wide text-muted">Cash</span>
          <span data-testid="cash-balance" className="font-semibold text-blue">
            {usd(cashBalance)}
          </span>
        </div>
        <div
          data-testid="connection-status"
          data-status={status}
          className="flex items-center gap-2"
          title={meta.label}
        >
          <span
            className="inline-block h-2.5 w-2.5 rounded-full"
            style={{ backgroundColor: meta.color }}
          />
          <span className="text-xs text-muted">{meta.label}</span>
        </div>
      </div>
    </header>
  );
}

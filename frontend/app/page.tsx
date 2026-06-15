"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { usePrices } from "@/lib/usePrices";
import type {
  ChatResponse,
  Portfolio,
  Snapshot,
  WatchlistItem,
} from "@/lib/types";
import { Header } from "@/components/Header";
import { Watchlist } from "@/components/Watchlist";
import { PriceChart } from "@/components/PriceChart";
import { PnlChart } from "@/components/PnlChart";
import { Heatmap } from "@/components/Heatmap";
import { PositionsTable } from "@/components/PositionsTable";
import { TradeBar } from "@/components/TradeBar";
import { ChatPanel } from "@/components/ChatPanel";

const EMPTY_PORTFOLIO: Portfolio = {
  cash_balance: 0,
  positions: [],
  positions_value: 0,
  total_value: 0,
  total_unrealized_pnl: 0,
};

export default function Home() {
  const { prices, history, status } = usePrices();
  const [portfolio, setPortfolio] = useState<Portfolio>(EMPTY_PORTFOLIO);
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [selected, setSelected] = useState<string | null>(null);

  const refreshPortfolio = useCallback(async () => {
    const [p, h] = await Promise.all([api.getPortfolio(), api.getHistory()]);
    setPortfolio(p);
    setSnapshots(h);
  }, []);

  const refreshWatchlist = useCallback(async () => {
    const w = await api.getWatchlist();
    setWatchlist(w);
    setSelected((cur) => cur ?? w[0]?.ticker ?? null);
  }, []);

  useEffect(() => {
    // Initial data fetch on mount; state is set asynchronously after await.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refreshPortfolio().catch(() => {});
    refreshWatchlist().catch(() => {});
  }, [refreshPortfolio, refreshWatchlist]);

  // Periodically refresh portfolio so live prices flow into P&L/positions.
  useEffect(() => {
    const id = setInterval(() => refreshPortfolio().catch(() => {}), 5000);
    return () => clearInterval(id);
  }, [refreshPortfolio]);

  const handleTrade = useCallback(
    async (ticker: string, quantity: number, side: "buy" | "sell") => {
      const res = await api.trade(ticker, quantity, side);
      setPortfolio(res.portfolio);
      refreshPortfolio().catch(() => {});
    },
    [refreshPortfolio],
  );

  const handleAdd = useCallback(async (ticker: string) => {
    const w = await api.addWatchlist(ticker).catch(() => null);
    if (w) setWatchlist(w);
  }, []);

  const handleRemove = useCallback(async (ticker: string) => {
    const w = await api.removeWatchlist(ticker).catch(() => null);
    if (w) setWatchlist(w);
  }, []);

  const handleChat = useCallback(
    async (message: string): Promise<ChatResponse> => {
      const res = await api.chat(message);
      // The AI may have traded or changed the watchlist; refresh both.
      refreshPortfolio().catch(() => {});
      refreshWatchlist().catch(() => {});
      return res;
    },
    [refreshPortfolio, refreshWatchlist],
  );

  return (
    <div className="flex h-screen flex-col bg-background text-foreground">
      <Header
        totalValue={portfolio.total_value}
        cashBalance={portfolio.cash_balance}
        status={status}
      />

      <main className="flex min-h-0 flex-1 gap-2 p-2">
        {/* Left column: watchlist */}
        <div className="w-72 shrink-0">
          <Watchlist
            items={watchlist}
            prices={prices}
            history={history}
            selected={selected}
            onSelect={setSelected}
            onAdd={handleAdd}
            onRemove={handleRemove}
          />
        </div>

        {/* Center column: charts, trade bar, positions */}
        <div className="flex min-w-0 flex-1 flex-col gap-2">
          <div className="grid min-h-0 flex-1 grid-cols-2 gap-2">
            <PriceChart ticker={selected} history={selected ? history[selected] ?? [] : []} />
            <PnlChart snapshots={snapshots} />
          </div>
          <TradeBar ticker={selected} onTrade={handleTrade} />
          <div className="grid min-h-0 flex-1 grid-cols-2 gap-2">
            <PositionsTable positions={portfolio.positions} prices={prices} onSelect={setSelected} />
            <Heatmap positions={portfolio.positions} />
          </div>
        </div>

        {/* Right column: AI chat */}
        <div className="shrink-0">
          <ChatPanel onSend={handleChat} />
        </div>
      </main>
    </div>
  );
}

/** Thin same-origin REST client for the backend /api/* endpoints. */

import type {
  ChatResponse,
  Portfolio,
  Snapshot,
  TradeResult,
  WatchlistItem,
} from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      // non-JSON error body; keep statusText
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  getPortfolio: () => request<Portfolio>("/api/portfolio"),

  getHistory: () => request<Snapshot[]>("/api/portfolio/history"),

  trade: (ticker: string, quantity: number, side: "buy" | "sell") =>
    request<TradeResult>("/api/portfolio/trade", {
      method: "POST",
      body: JSON.stringify({ ticker, quantity, side }),
    }),

  getWatchlist: () => request<WatchlistItem[]>("/api/watchlist"),

  addWatchlist: (ticker: string) =>
    request<WatchlistItem[]>("/api/watchlist", {
      method: "POST",
      body: JSON.stringify({ ticker }),
    }),

  removeWatchlist: (ticker: string) =>
    request<WatchlistItem[]>(`/api/watchlist/${encodeURIComponent(ticker)}`, {
      method: "DELETE",
    }),

  chat: (message: string) =>
    request<ChatResponse>("/api/chat", {
      method: "POST",
      body: JSON.stringify({ message }),
    }),
};

/** Wire types shared with the backend REST/SSE API. */

export interface PriceUpdate {
  ticker: string;
  price: number;
  previous_price: number;
  timestamp: number;
  change: number;
  change_percent: number;
  direction: "up" | "down" | "flat";
}

/** SSE event payload: an object keyed by ticker. */
export type PriceMap = Record<string, PriceUpdate>;

export interface Position {
  ticker: string;
  quantity: number;
  avg_cost: number;
  current_price: number;
  market_value: number;
  unrealized_pnl: number;
  unrealized_pnl_percent: number;
}

export interface Portfolio {
  cash_balance: number;
  positions: Position[];
  positions_value: number;
  total_value: number;
  total_unrealized_pnl: number;
}

export interface Trade {
  id: string;
  ticker: string;
  side: "buy" | "sell";
  quantity: number;
  price: number;
  executed_at: string;
}

export interface TradeResult {
  trade: Trade;
  portfolio: Portfolio;
}

export interface Snapshot {
  total_value: number;
  recorded_at: string;
}

export interface WatchlistItem {
  ticker: string;
  price: number | null;
  previous_price: number | null;
  change: number | null;
  change_percent: number | null;
  direction: "up" | "down" | "flat" | null;
}

/** Executed result of an AI-issued trade. */
export interface TradeAction {
  type: "trade";
  status: "executed" | "error";
  ticker: string;
  side: "buy" | "sell";
  quantity: number;
  price?: number; // present when executed
  error?: string; // present when status === "error"
}

/** Executed result of an AI-issued watchlist change. */
export interface WatchlistAction {
  type: "watchlist";
  status: "executed" | "noop";
  ticker: string;
  action: "add" | "remove";
}

export type ChatAction = TradeAction | WatchlistAction;

export interface ChatResponse {
  message: string;
  actions: ChatAction[];
}

export type ConnectionStatus = "connected" | "reconnecting" | "disconnected";

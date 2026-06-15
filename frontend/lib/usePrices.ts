"use client";

import { useEffect, useRef, useState } from "react";
import type { ConnectionStatus, PriceMap, PriceUpdate } from "./types";

const SPARK_LEN = 60; // points retained per ticker for sparklines

export interface PricesState {
  prices: PriceMap;
  /** Per-ticker price history accumulated since page load, for sparklines. */
  history: Record<string, number[]>;
  status: ConnectionStatus;
}

/**
 * Subscribes to GET /api/stream/prices via EventSource. Maintains the latest
 * price map, a bounded per-ticker price history for sparklines, and the
 * connection status. EventSource handles reconnection automatically.
 */
export function usePrices(): PricesState {
  const [prices, setPrices] = useState<PriceMap>({});
  const [status, setStatus] = useState<ConnectionStatus>("reconnecting");
  const historyRef = useRef<Record<string, number[]>>({});
  const [history, setHistory] = useState<Record<string, number[]>>({});

  useEffect(() => {
    const source = new EventSource("/api/stream/prices");

    source.onopen = () => setStatus("connected");

    source.onmessage = (event) => {
      const data = JSON.parse(event.data) as PriceMap;
      setPrices(data);

      const next = { ...historyRef.current };
      for (const [ticker, update] of Object.entries(data)) {
        const series = next[ticker] ? [...next[ticker]] : [];
        series.push((update as PriceUpdate).price);
        if (series.length > SPARK_LEN) series.shift();
        next[ticker] = series;
      }
      historyRef.current = next;
      setHistory(next);
      setStatus("connected");
    };

    source.onerror = () => {
      // EventSource auto-retries; CLOSED is terminal, otherwise reconnecting.
      setStatus(source.readyState === EventSource.CLOSED ? "disconnected" : "reconnecting");
    };

    return () => source.close();
  }, []);

  return { prices, history, status };
}

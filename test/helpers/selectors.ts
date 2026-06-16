/**
 * Central data-testid selectors. Kept in one place so they can be reconciled
 * with the frontend's actual testids once the UI lands (see message to
 * frontend-engineer). Update here, not in individual specs.
 */
export const tid = (id: string) => `[data-testid="${id}"]`;

export const sel = {
  cashBalance: tid("cash-balance"),
  totalValue: tid("total-value"),
  connectionStatus: tid("connection-status"),

  watchlist: tid("watchlist"),
  watchlistRow: (t: string) => tid(`watchlist-row-${t}`),
  watchlistAddInput: tid("watchlist-add-input"),
  watchlistAddBtn: tid("watchlist-add-btn"),
  watchlistRemove: (t: string) => tid(`watchlist-remove-${t}`),

  tradeTicker: tid("trade-ticker"),
  tradeQuantity: tid("trade-quantity"),
  tradeBuyBtn: tid("trade-buy-btn"),
  tradeSellBtn: tid("trade-sell-btn"),

  positionsTable: tid("positions-table"),
  positionRow: (t: string) => tid(`position-row-${t}`),

  portfolioHeatmap: tid("portfolio-heatmap"),
  pnlChart: tid("pnl-chart"),
  priceChart: tid("price-chart"),

  chatInput: tid("chat-input"),
  chatSendBtn: tid("chat-send-btn"),
  chatMessage: tid("chat-message"),
  chatAction: tid("chat-action"),
};

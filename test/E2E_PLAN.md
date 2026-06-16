# FinAlly E2E Test Plan (Task #6)

Playwright E2E tests covering PLAN.md Section 12. Tests run against the full
stack (FastAPI serving the Next.js static export on port 8000) with
`LLM_MOCK=true` for deterministic, free, fast chat tests and the built-in
market simulator (no `MASSIVE_API_KEY`).

## How it runs

- `docker-compose.test.yml` builds/starts the app image and a Playwright
  runner, OR tests run locally against `http://localhost:8000` via
  `BASE_URL`.
- `LLM_MOCK=true`, `MASSIVE_API_KEY` unset, fresh ephemeral SQLite DB per run.
- Readiness gate: poll `GET /api/health` until 200 before tests start.

## Data contract assumptions (verify with teammates)

- Seed: cash $10,000; watchlist AAPL, GOOGL, MSFT, AMZN, TSLA, NVDA, META, JPM, V, NFLX.
- SSE `GET /api/stream/prices` pushes one event whose `data:` is a JSON object
  keyed by ticker: `{"AAPL": {ticker, price, previous_price, timestamp, change, change_percent, direction}, ...}`.
- REST shapes per PLAN.md Section 8.
- Mock chat behavior: TBD from llm-engineer (need deterministic trigger for a
  trade and a watchlist change).
- Frontend `data-testid`s: TBD from frontend-engineer.

## Scenarios

1. **Fresh start** — default 10-ticker watchlist renders; cash $10,000 shown;
   total value shown; prices stream (a price updates within a few seconds);
   connection indicator goes green.
2. **Add + remove watchlist ticker** — add a new ticker (e.g. PYPL), row
   appears and streams a price; remove it, row disappears.
3. **Buy shares** — buy N shares of a watched ticker; cash decreases by
   ~price*N; position row appears with correct qty; total value reflects it.
4. **Sell shares** — sell some/all of a held position; cash increases;
   position qty decreases or row disappears when zeroed.
5. **Portfolio visualization** — after holding positions, heatmap renders
   rectangles (colored by P&L sign) and P&L chart has >= 1 data point.
6. **AI chat (mocked)** — send a message, receive the deterministic mock
   response; when the mock includes a trade/watchlist change, the inline
   action confirmation appears and portfolio/watchlist reflects it.
7. **SSE resilience** — interrupt the stream (offline/online or navigation),
   verify EventSource reconnects and prices resume; connection indicator
   recovers to green.

## Invariants checked across tests

- No uncaught console errors / page errors during a scenario.
- API error responses surface as user-visible messages, not silent failures
  (e.g. buy with insufficient cash).

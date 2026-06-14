# Market Simulator

The approach and code structure for simulating realistic, correlated stock
prices when no `MASSIVE_API_KEY` is set. It implements the same
`MarketDataSource` contract as the real client (see
[MARKET_INTERFACE.md](MARKET_INTERFACE.md)), so downstream code cannot tell the
difference.

## Goals

- **Realistic motion** — prices drift and wobble like real equities, not random
  noise.
- **Correlated moves** — tech stocks tend to move together; finance together;
  TSLA does its own thing. Makes the heatmap and watchlist feel alive.
- **Visual drama** — occasional sudden 2-5% shocks so the terminal has events to
  flash.
- **Zero dependencies** — pure in-process background task; no network, no key.
- **Fast hot path** — runs every ~500ms; the per-tick step must stay cheap.

## Model: Geometric Brownian Motion (GBM)

The standard model for stock prices. Each tick advances every ticker by:

```
S(t+dt) = S(t) * exp( (mu - sigma^2/2) * dt  +  sigma * sqrt(dt) * Z )
```

| Symbol | Meaning |
|--------|---------|
| `S(t)` | current price |
| `mu` | annualized drift (expected return) |
| `sigma` | annualized volatility |
| `dt` | time step as a fraction of a trading year |
| `Z` | a *correlated* standard-normal draw |

### Choosing `dt`

`dt` is a 500ms tick expressed in trading-years:

```
TRADING_SECONDS_PER_YEAR = 252 * 6.5 * 3600   # = 5,896,800
DEFAULT_DT = 0.5 / TRADING_SECONDS_PER_YEAR    # ≈ 8.48e-8
```

This tiny `dt` produces sub-cent moves per tick that accumulate naturally into
believable intraday drift — no artificial scaling needed.

## Correlated Moves via Cholesky

Independent random draws would make every ticker wander on its own. Real sectors
co-move. We build a correlation matrix and apply its **Cholesky decomposition** to
independent normals to get correlated ones.

```
z_independent ~ N(0, I)        # n independent draws
z_correlated  = L @ z_independent   # L = cholesky(correlation_matrix)
```

Correlation structure (pairwise):

| Pair | Correlation |
|------|-------------|
| Same tech sector | 0.6 |
| Same finance sector | 0.5 |
| TSLA with anything | 0.3 (independent-ish) |
| Cross-sector | 0.3 |
| Unknown ticker | 0.3 |

The matrix is rebuilt only when tickers are added/removed (O(n²), but n < 50, so
negligible).

## Random Shock Events

On each tick, each ticker has a ~0.1% chance (`event_probability = 0.001`) of a
sudden jump:

```python
if random.random() < self._event_prob:
    shock = random.uniform(0.02, 0.05) * random.choice([-1, 1])  # ±2–5%
    self._prices[ticker] *= (1 + shock)
```

With 10 tickers at 2 ticks/sec, expect an event roughly every ~50 seconds —
frequent enough for drama, rare enough to stay realistic.

## Seed Data

`seed_prices.py` holds the starting conditions:

- **`SEED_PRICES`** — realistic opening prices (e.g. AAPL ~190, GOOGL ~175).
  Unknown tickers get a random price in `[50, 300]`.
- **`TICKER_PARAMS`** — per-ticker `{"mu", "sigma"}`. Unknown tickers fall back to
  `DEFAULT_PARAMS`.
- **`CORRELATION_GROUPS`** — `{"tech": {...}, "finance": {...}}` sector membership.
- Correlation constants: `INTRA_TECH_CORR`, `INTRA_FINANCE_CORR`, `TSLA_CORR`,
  `CROSS_GROUP_CORR`.

## Code Structure

Two classes, separating the math from the lifecycle.

### `GBMSimulator` — the math engine

Pure, synchronous, no asyncio. Owns price state and the correlation matrix.

```python
class GBMSimulator:
    def __init__(self, tickers, dt=DEFAULT_DT, event_probability=0.001): ...

    def step(self) -> dict[str, float]:
        """Advance all tickers one tick. Returns {ticker: new_price}. Hot path."""

    def add_ticker(self, ticker: str) -> None:    # seeds price + params, rebuilds Cholesky
    def remove_ticker(self, ticker: str) -> None: # drops state, rebuilds Cholesky
    def get_price(self, ticker: str) -> float | None: ...
    def get_tickers(self) -> list[str]: ...
```

`step()` is the hot path: one vectorized `np.random.standard_normal(n)` draw, one
matrix multiply for correlation, then the GBM update per ticker, prices rounded
to cents.

### `SimulatorDataSource` — the lifecycle wrapper

Implements `MarketDataSource`. Runs the asyncio loop and writes to the cache.

```python
class SimulatorDataSource(MarketDataSource):
    def __init__(self, price_cache, update_interval=0.5, event_probability=0.001): ...

    async def start(self, tickers):
        # build GBMSimulator, seed cache with initial prices, launch _run_loop
    async def stop(self):     # cancel task, await CancelledError
    async def add_ticker(self, ticker):     # add to sim, seed cache immediately
    async def remove_ticker(self, ticker):  # remove from sim and cache
    def get_tickers(self): ...

    async def _run_loop(self):
        while True:
            prices = self._sim.step()
            for ticker, price in prices.items():
                self._cache.update(ticker=ticker, price=price)
            await asyncio.sleep(self._interval)
```

Key behaviors:
- `start()` seeds the cache with initial prices **before** the loop runs, so SSE
  has data on the first client connection.
- `add_ticker()` seeds the new ticker's price into the cache immediately rather
  than waiting up to 500ms for the next tick.
- The loop wraps `step()` in a `try/except` that logs and continues — one bad
  step never kills the simulation.

## Why GBM + Cholesky (not simpler noise)

| Choice | Rationale |
|--------|-----------|
| GBM | Industry-standard price model; prices stay positive, moves are multiplicative |
| Annualized `mu`/`sigma` with tiny `dt` | Lets us reason in familiar terms; natural-looking sub-cent ticks |
| Cholesky-correlated draws | Sectors co-move → realistic heatmap and watchlist behavior |
| Rare ±2–5% shocks | Visual events for the terminal without dominating the signal |
| Split math vs. lifecycle | `GBMSimulator` is easily unit-tested in isolation from asyncio |

# Unified Market Data Interface

The design of the single Python API the project uses to retrieve stock prices.
It selects the **Massive API** when `MASSIVE_API_KEY` is set, otherwise the
**simulator** ([MARKET_SIMULATOR.md](MARKET_SIMULATOR.md)). All downstream code
(SSE streaming, portfolio valuation, trade execution) is agnostic to the source.

Grounded in the real-data shape documented in [MASSIVE_API.md](MASSIVE_API.md).

## Design Goals

- **One contract, two implementations** — swap data sources via an env var with
  zero downstream changes (Strategy pattern).
- **Decoupled producers and consumers** — the data source *writes* prices into a
  shared cache; consumers *read* from the cache. They never call each other.
- **Push-friendly** — the cache carries a version counter so the SSE endpoint can
  detect changes cheaply without polling each ticker.
- **Single API call for live data** — the Massive poller fetches all tickers in
  one snapshot request to respect the free-tier rate limit.

## Architecture

```
            create_market_data_source(cache)   ← reads MASSIVE_API_KEY
                       │
        ┌──────────────┴───────────────┐
        ▼                              ▼
SimulatorDataSource            MassiveDataSource
 (GBM, ~500ms ticks)            (REST poll, 15s default)
        │                              │
        └──────────────┬───────────────┘
                       ▼
                  PriceCache                ← single source of truth
                 (thread-safe)
                       │
        ┌──────────────┼───────────────┐
        ▼              ▼               ▼
   SSE stream    Portfolio val.   Trade execution
```

## The Contract: `MarketDataSource`

An abstract base class. Both sources implement it identically.

```python
from abc import ABC, abstractmethod


class MarketDataSource(ABC):
    """Contract for market data providers.

    Implementations push price updates into a shared PriceCache on their own
    schedule. Downstream code reads from the cache, never from the source.

    Lifecycle:
        source = create_market_data_source(cache)
        await source.start(["AAPL", "GOOGL", ...])
        await source.add_ticker("TSLA")
        await source.remove_ticker("GOOGL")
        await source.stop()
    """

    @abstractmethod
    async def start(self, tickers: list[str]) -> None:
        """Start the background producer task. Call exactly once."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop the task and release resources. Safe to call repeatedly."""

    @abstractmethod
    async def add_ticker(self, ticker: str) -> None:
        """Add a ticker to the active set. No-op if already present."""

    @abstractmethod
    async def remove_ticker(self, ticker: str) -> None:
        """Remove a ticker; also drop it from the cache. No-op if absent."""

    @abstractmethod
    def get_tickers(self) -> list[str]:
        """Return the currently tracked tickers."""
```

Lifecycle rules:
- `start()` does an **immediate first fetch** so the cache has data before any
  client connects, then launches the background task.
- `stop()` cancels the task and awaits its `CancelledError`; idempotent.
- `add_ticker` / `remove_ticker` mutate the active set live; the next cycle
  reflects the change. Removal also evicts from the cache.

## `PriceUpdate` — the unit of data

An immutable frozen dataclass produced by the cache on every update.

```python
@dataclass(frozen=True)
class PriceUpdate:
    ticker: str
    price: float
    previous_price: float | None
    timestamp: float                 # epoch seconds

    @property
    def change(self) -> float: ...           # price - previous_price
    @property
    def change_percent(self) -> float: ...
    @property
    def direction(self) -> str: ...          # "up" | "down" | "flat"

    def to_dict(self) -> dict: ...           # JSON for SSE payloads
```

## `PriceCache` — single source of truth

Thread-safe in-memory store. The Massive poller writes from a worker thread; the
simulator writes from the event loop — so the lock matters.

```python
class PriceCache:
    def update(self, ticker: str, price: float, timestamp: float | None = None) -> PriceUpdate:
        """Store a new price, compute previous/change, bump version."""

    def get(self, ticker: str) -> PriceUpdate | None: ...
    def get_price(self, ticker: str) -> float | None: ...
    def get_all(self) -> dict[str, PriceUpdate]: ...
    def remove(self, ticker: str) -> None: ...

    @property
    def version(self) -> int:
        """Monotonic counter; increments on every update. SSE change detection."""
```

`update()` carries the prior price into `previous_price`, so price-flash
direction is derived in one place regardless of source.

## The Factory

The only place that knows about the env var. Everything else depends on the ABC.

```python
import os
from .cache import PriceCache
from .interface import MarketDataSource
from .simulator import SimulatorDataSource
from .massive_client import MassiveDataSource


def create_market_data_source(cache: PriceCache) -> MarketDataSource:
    """Return MassiveDataSource if MASSIVE_API_KEY is set, else the simulator."""
    api_key = os.environ.get("MASSIVE_API_KEY", "").strip()
    if api_key:
        return MassiveDataSource(api_key=api_key, price_cache=cache)
    return SimulatorDataSource(price_cache=cache)
```

Selection is purely presence-of-key. Empty or whitespace-only is treated as
unset → simulator.

## Massive Implementation Notes

`MassiveDataSource` polls the **full snapshot** endpoint for all watched tickers
in one request (see [MASSIVE_API.md](MASSIVE_API.md) §1):

- Default poll interval **15s** (free tier safe); lower on paid tiers.
- The synchronous `RESTClient` call runs via `asyncio.to_thread` so it never
  blocks the loop.
- Each snapshot maps to `cache.update(ticker, price, timestamp/1000.0)`.
- Broad `try/except` around the poll; per-snapshot parse errors skip just that
  ticker. The loop always retries on the next interval — a transient 429/network
  error never crashes the app.

## Simulator Implementation Notes

`SimulatorDataSource` steps a GBM model every ~500ms and writes all prices to the
cache. No external dependencies. Full approach in
[MARKET_SIMULATOR.md](MARKET_SIMULATOR.md).

## Usage From The App

```python
from app.market import PriceCache, create_market_data_source

# Startup
cache = PriceCache()
source = create_market_data_source(cache)   # picks source from env
await source.start(["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA",
                    "NVDA", "META", "JPM", "V", "NFLX"])

# Anywhere downstream — read from the cache, not the source
update = cache.get("AAPL")        # PriceUpdate | None
price = cache.get_price("AAPL")   # float | None
everything = cache.get_all()      # dict[str, PriceUpdate]

# Live watchlist edits
await source.add_ticker("PYPL")
await source.remove_ticker("GOOGL")

# Shutdown
await source.stop()
```

## Why This Shape

| Choice | Rationale |
|--------|-----------|
| ABC + factory | Add/replace a source without touching consumers |
| Cache as the seam | Producers and consumers fully decoupled; supports multi-user later |
| Version counter | SSE detects "something changed" in O(1), no per-ticker diffing |
| Push into cache (not pull) | Same model for a 500ms simulator and a 15s REST poll |
| Single snapshot call | One request covers all tickers → fits free-tier rate limit |

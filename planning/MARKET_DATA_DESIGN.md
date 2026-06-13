# Market Data Backend — Detailed Design

A complete, implementation-ready design for the FinAlly market data subsystem.
It covers the unified interface, the GBM simulator, the Massive (Polygon.io) REST
client, the shared price cache, the factory, and the SSE streaming endpoint, with
full code for every module.

Companion documents:
- [MARKET_INTERFACE.md](MARKET_INTERFACE.md) — the unified-API design rationale
- [MARKET_SIMULATOR.md](MARKET_SIMULATOR.md) — the simulation approach
- [MASSIVE_API.md](MASSIVE_API.md) — the Massive API reference
- [PLAN.md](PLAN.md) §6 — product requirements

## 1. Overview

```
            create_market_data_source(cache)     ← reads MASSIVE_API_KEY
                          │
          ┌───────────────┴────────────────┐
          ▼                                ▼
  SimulatorDataSource              MassiveDataSource
   GBM, ~500ms ticks               REST poll, 15s default
   (default, no key)               (when key is set)
          │                                │
          └───────────────┬────────────────┘
                          ▼  writes
                     PriceCache               ← single source of truth
                   thread-safe, versioned
                          │  reads
          ┌───────────────┼────────────────┐
          ▼               ▼                ▼
   SSE /api/stream/   portfolio val.   trade execution
       prices
```

**Core principle:** producers (sources) *write* into the cache on their own
schedule; consumers *read* from the cache. They are fully decoupled — neither
the SSE endpoint nor portfolio code ever touches a data source directly.

### Module layout (`backend/app/market/`)

| Module | Responsibility |
|--------|----------------|
| `models.py` | `PriceUpdate` immutable dataclass |
| `cache.py` | `PriceCache` thread-safe versioned store |
| `interface.py` | `MarketDataSource` ABC |
| `seed_prices.py` | seed prices, GBM params, correlation config |
| `simulator.py` | `GBMSimulator` + `SimulatorDataSource` |
| `massive_client.py` | `MassiveDataSource` REST poller |
| `factory.py` | `create_market_data_source()` |
| `stream.py` | `create_stream_router()` SSE endpoint |
| `__init__.py` | public exports |

### Dependencies

```toml
# pyproject.toml
dependencies = [
    "fastapi",
    "numpy",       # Cholesky + vectorized normal draws in the simulator
    "massive",     # Massive (Polygon.io) Python client
]

[tool.hatch.build.targets.wheel]
packages = ["app"]
```

## 2. `models.py` — PriceUpdate

The unit of data flowing through the system. Immutable, frozen, slotted.

```python
"""Data models for market data."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class PriceUpdate:
    """Immutable snapshot of a single ticker's price at a point in time."""

    ticker: str
    price: float
    previous_price: float
    timestamp: float = field(default_factory=time.time)  # Unix seconds

    @property
    def change(self) -> float:
        """Absolute price change from previous update."""
        return round(self.price - self.previous_price, 4)

    @property
    def change_percent(self) -> float:
        """Percentage change from previous update."""
        if self.previous_price == 0:
            return 0.0
        return round((self.price - self.previous_price) / self.previous_price * 100, 4)

    @property
    def direction(self) -> str:
        """'up', 'down', or 'flat' — drives the frontend price-flash."""
        if self.price > self.previous_price:
            return "up"
        elif self.price < self.previous_price:
            return "down"
        return "flat"

    def to_dict(self) -> dict:
        """Serialize for JSON / SSE transmission."""
        return {
            "ticker": self.ticker,
            "price": self.price,
            "previous_price": self.previous_price,
            "timestamp": self.timestamp,
            "change": self.change,
            "change_percent": self.change_percent,
            "direction": self.direction,
        }
```

Design notes:
- `change`/`change_percent`/`direction` are derived properties, not stored — one
  place defines them, both sources get identical semantics.
- `frozen=True` makes instances safe to share across threads (the Massive poller
  runs in a worker thread; the SSE reader runs on the loop).

## 3. `cache.py` — PriceCache

The seam between producers and consumers. Thread-safe because the Massive client
writes from `asyncio.to_thread` while readers run on the event loop.

```python
"""Thread-safe in-memory price cache."""

from __future__ import annotations

import time
from threading import Lock

from .models import PriceUpdate


class PriceCache:
    """Thread-safe in-memory cache of the latest price for each ticker.

    Writers: SimulatorDataSource or MassiveDataSource (one at a time).
    Readers: SSE streaming endpoint, portfolio valuation, trade execution.
    """

    def __init__(self) -> None:
        self._prices: dict[str, PriceUpdate] = {}
        self._lock = Lock()
        self._version: int = 0  # Monotonically increasing; bumped on every update

    def update(self, ticker: str, price: float, timestamp: float | None = None) -> PriceUpdate:
        """Record a new price. Computes previous_price/change/direction.

        On the first update for a ticker, previous_price == price (direction 'flat').
        """
        with self._lock:
            ts = timestamp or time.time()
            prev = self._prices.get(ticker)
            previous_price = prev.price if prev else price

            update = PriceUpdate(
                ticker=ticker,
                price=round(price, 2),
                previous_price=round(previous_price, 2),
                timestamp=ts,
            )
            self._prices[ticker] = update
            self._version += 1
            return update

    def get(self, ticker: str) -> PriceUpdate | None:
        with self._lock:
            return self._prices.get(ticker)

    def get_all(self) -> dict[str, PriceUpdate]:
        """Shallow copy snapshot of all current prices."""
        with self._lock:
            return dict(self._prices)

    def get_price(self, ticker: str) -> float | None:
        update = self.get(ticker)
        return update.price if update else None

    def remove(self, ticker: str) -> None:
        with self._lock:
            self._prices.pop(ticker, None)

    @property
    def version(self) -> int:
        """Monotonic counter, bumped on every update. SSE change detection."""
        return self._version

    def __len__(self) -> int:
        with self._lock:
            return len(self._prices)

    def __contains__(self, ticker: str) -> bool:
        with self._lock:
            return ticker in self._prices
```

The `version` counter is the trick that lets the SSE endpoint detect "something
changed" in O(1) without diffing every ticker.

## 4. `interface.py` — MarketDataSource

The contract. Both sources implement it identically; downstream depends only on
this ABC.

```python
"""Abstract interface for market data sources."""

from __future__ import annotations

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
        """Begin producing updates. Starts a background task. Call once."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop the task, release resources. Safe to call repeatedly."""

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

## 5. `seed_prices.py` — simulator configuration

```python
"""Seed prices and per-ticker parameters for the market simulator."""

# Realistic starting prices for the default watchlist
SEED_PRICES: dict[str, float] = {
    "AAPL": 190.00, "GOOGL": 175.00, "MSFT": 420.00, "AMZN": 185.00,
    "TSLA": 250.00, "NVDA": 800.00, "META": 500.00, "JPM": 195.00,
    "V": 280.00, "NFLX": 600.00,
}

# Per-ticker GBM parameters.
#   sigma: annualized volatility (higher = more movement)
#   mu:    annualized drift / expected return
TICKER_PARAMS: dict[str, dict[str, float]] = {
    "AAPL": {"sigma": 0.22, "mu": 0.05},
    "GOOGL": {"sigma": 0.25, "mu": 0.05},
    "MSFT": {"sigma": 0.20, "mu": 0.05},
    "AMZN": {"sigma": 0.28, "mu": 0.05},
    "TSLA": {"sigma": 0.50, "mu": 0.03},   # high volatility
    "NVDA": {"sigma": 0.40, "mu": 0.08},   # high volatility, strong drift
    "META": {"sigma": 0.30, "mu": 0.05},
    "JPM": {"sigma": 0.18, "mu": 0.04},    # low volatility (bank)
    "V": {"sigma": 0.17, "mu": 0.04},      # low volatility (payments)
    "NFLX": {"sigma": 0.35, "mu": 0.05},
}

# Fallback for dynamically added tickers not listed above
DEFAULT_PARAMS: dict[str, float] = {"sigma": 0.25, "mu": 0.05}

# Sector membership for Cholesky correlation
CORRELATION_GROUPS: dict[str, set[str]] = {
    "tech": {"AAPL", "GOOGL", "MSFT", "AMZN", "META", "NVDA", "NFLX"},
    "finance": {"JPM", "V"},
}

# Correlation coefficients
INTRA_TECH_CORR = 0.6      # tech stocks move together
INTRA_FINANCE_CORR = 0.5   # finance stocks move together
CROSS_GROUP_CORR = 0.3     # between sectors / unknown tickers
TSLA_CORR = 0.3            # TSLA does its own thing
```

## 6. `simulator.py` — GBM Simulator

Two classes: `GBMSimulator` (pure math, synchronous, unit-testable) and
`SimulatorDataSource` (asyncio lifecycle, writes to cache). See
[MARKET_SIMULATOR.md](MARKET_SIMULATOR.md) for the model derivation.

### 6.1 GBMSimulator — the math engine

```python
"""GBM-based market simulator."""

from __future__ import annotations

import logging
import math
import random

import numpy as np

from .seed_prices import (
    CORRELATION_GROUPS, CROSS_GROUP_CORR, DEFAULT_PARAMS,
    INTRA_FINANCE_CORR, INTRA_TECH_CORR, SEED_PRICES, TICKER_PARAMS, TSLA_CORR,
)

logger = logging.getLogger(__name__)


class GBMSimulator:
    """Geometric Brownian Motion simulator for correlated stock prices.

        S(t+dt) = S(t) * exp((mu - sigma^2/2) * dt + sigma * sqrt(dt) * Z)

    Z is a *correlated* standard-normal draw (Cholesky of the sector matrix).
    """

    # 500ms as a fraction of a trading year:
    #   252 trading days * 6.5 hours * 3600 sec = 5,896,800 sec
    TRADING_SECONDS_PER_YEAR = 252 * 6.5 * 3600
    DEFAULT_DT = 0.5 / TRADING_SECONDS_PER_YEAR  # ~8.48e-8

    def __init__(self, tickers, dt=DEFAULT_DT, event_probability=0.001) -> None:
        self._dt = dt
        self._event_prob = event_probability
        self._tickers: list[str] = []
        self._prices: dict[str, float] = {}
        self._params: dict[str, dict[str, float]] = {}
        self._cholesky: np.ndarray | None = None

        for ticker in tickers:
            self._add_ticker_internal(ticker)
        self._rebuild_cholesky()

    def step(self) -> dict[str, float]:
        """Advance all tickers one tick. Returns {ticker: new_price}. Hot path."""
        n = len(self._tickers)
        if n == 0:
            return {}

        z = np.random.standard_normal(n)
        if self._cholesky is not None:
            z = self._cholesky @ z   # correlate the draws

        result: dict[str, float] = {}
        for i, ticker in enumerate(self._tickers):
            p = self._params[ticker]
            mu, sigma = p["mu"], p["sigma"]

            drift = (mu - 0.5 * sigma**2) * self._dt
            diffusion = sigma * math.sqrt(self._dt) * z[i]
            self._prices[ticker] *= math.exp(drift + diffusion)

            # Rare shock event for visual drama (~0.1%/tick/ticker)
            if random.random() < self._event_prob:
                shock = random.uniform(0.02, 0.05) * random.choice([-1, 1])
                self._prices[ticker] *= 1 + shock
                logger.debug("Event on %s: %.1f%%", ticker, shock * 100)

            result[ticker] = round(self._prices[ticker], 2)
        return result

    def add_ticker(self, ticker: str) -> None:
        if ticker in self._prices:
            return
        self._add_ticker_internal(ticker)
        self._rebuild_cholesky()

    def remove_ticker(self, ticker: str) -> None:
        if ticker not in self._prices:
            return
        self._tickers.remove(ticker)
        del self._prices[ticker]
        del self._params[ticker]
        self._rebuild_cholesky()

    def get_price(self, ticker: str) -> float | None:
        return self._prices.get(ticker)

    def get_tickers(self) -> list[str]:
        return list(self._tickers)

    # --- internals ---

    def _add_ticker_internal(self, ticker: str) -> None:
        if ticker in self._prices:
            return
        self._tickers.append(ticker)
        self._prices[ticker] = SEED_PRICES.get(ticker, random.uniform(50.0, 300.0))
        self._params[ticker] = TICKER_PARAMS.get(ticker, dict(DEFAULT_PARAMS))

    def _rebuild_cholesky(self) -> None:
        """Rebuild Cholesky of the correlation matrix. O(n^2), n < 50."""
        n = len(self._tickers)
        if n <= 1:
            self._cholesky = None
            return
        corr = np.eye(n)
        for i in range(n):
            for j in range(i + 1, n):
                rho = self._pairwise_correlation(self._tickers[i], self._tickers[j])
                corr[i, j] = corr[j, i] = rho
        self._cholesky = np.linalg.cholesky(corr)

    @staticmethod
    def _pairwise_correlation(t1: str, t2: str) -> float:
        tech = CORRELATION_GROUPS["tech"]
        finance = CORRELATION_GROUPS["finance"]
        if t1 == "TSLA" or t2 == "TSLA":
            return TSLA_CORR
        if t1 in tech and t2 in tech:
            return INTRA_TECH_CORR
        if t1 in finance and t2 in finance:
            return INTRA_FINANCE_CORR
        return CROSS_GROUP_CORR
```

### 6.2 SimulatorDataSource — the lifecycle wrapper

```python
import asyncio

from .cache import PriceCache
from .interface import MarketDataSource


class SimulatorDataSource(MarketDataSource):
    """MarketDataSource backed by the GBM simulator.

    Runs a background asyncio task that steps the simulation every
    `update_interval` seconds and writes results to the PriceCache.
    """

    def __init__(self, price_cache: PriceCache, update_interval=0.5, event_probability=0.001):
        self._cache = price_cache
        self._interval = update_interval
        self._event_prob = event_probability
        self._sim: GBMSimulator | None = None
        self._task: asyncio.Task | None = None

    async def start(self, tickers: list[str]) -> None:
        self._sim = GBMSimulator(tickers=tickers, event_probability=self._event_prob)
        # Seed the cache immediately so SSE has data on first connect
        for ticker in tickers:
            price = self._sim.get_price(ticker)
            if price is not None:
                self._cache.update(ticker=ticker, price=price)
        self._task = asyncio.create_task(self._run_loop(), name="simulator-loop")
        logger.info("Simulator started with %d tickers", len(tickers))

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        logger.info("Simulator stopped")

    async def add_ticker(self, ticker: str) -> None:
        if self._sim:
            self._sim.add_ticker(ticker)
            price = self._sim.get_price(ticker)
            if price is not None:
                self._cache.update(ticker=ticker, price=price)

    async def remove_ticker(self, ticker: str) -> None:
        if self._sim:
            self._sim.remove_ticker(ticker)
        self._cache.remove(ticker)

    def get_tickers(self) -> list[str]:
        return self._sim.get_tickers() if self._sim else []

    async def _run_loop(self) -> None:
        while True:
            try:
                if self._sim:
                    for ticker, price in self._sim.step().items():
                        self._cache.update(ticker=ticker, price=price)
            except Exception:
                logger.exception("Simulator step failed")
            await asyncio.sleep(self._interval)
```

## 7. `massive_client.py` — Massive REST Poller

Polls the full-snapshot endpoint for all tickers in **one** request (free-tier
safe). The `RESTClient` is synchronous, so the HTTP call runs in a worker thread.
See [MASSIVE_API.md](MASSIVE_API.md) for endpoint/field details.

```python
"""Massive (Polygon.io) API client for real market data."""

from __future__ import annotations

import asyncio
import logging

from massive import RESTClient
from massive.rest.models import SnapshotMarketType

from .cache import PriceCache
from .interface import MarketDataSource

logger = logging.getLogger(__name__)


class MassiveDataSource(MarketDataSource):
    """MarketDataSource backed by the Massive (Polygon.io) REST API.

    Polls GET /v2/snapshot/locale/us/markets/stocks/tickers for all watched
    tickers in a single call, then writes results to the PriceCache.

    Rate limits:
      - Free tier: 5 req/min  -> poll every 15s (default)
      - Paid tiers: higher    -> poll every 2-5s
    """

    def __init__(self, api_key: str, price_cache: PriceCache, poll_interval: float = 15.0):
        self._api_key = api_key
        self._cache = price_cache
        self._interval = poll_interval
        self._tickers: list[str] = []
        self._task: asyncio.Task | None = None
        self._client: RESTClient | None = None

    async def start(self, tickers: list[str]) -> None:
        self._client = RESTClient(api_key=self._api_key)
        self._tickers = list(tickers)
        await self._poll_once()  # immediate first poll so cache has data
        self._task = asyncio.create_task(self._poll_loop(), name="massive-poller")
        logger.info("Massive poller started: %d tickers, %.1fs interval",
                    len(tickers), self._interval)

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        self._client = None
        logger.info("Massive poller stopped")

    async def add_ticker(self, ticker: str) -> None:
        ticker = ticker.upper().strip()
        if ticker not in self._tickers:
            self._tickers.append(ticker)

    async def remove_ticker(self, ticker: str) -> None:
        ticker = ticker.upper().strip()
        self._tickers = [t for t in self._tickers if t != ticker]
        self._cache.remove(ticker)

    def get_tickers(self) -> list[str]:
        return list(self._tickers)

    # --- internals ---

    async def _poll_loop(self) -> None:
        while True:
            await asyncio.sleep(self._interval)
            await self._poll_once()

    async def _poll_once(self) -> None:
        if not self._tickers or not self._client:
            return
        try:
            # RESTClient is synchronous -> run off the event loop
            snapshots = await asyncio.to_thread(self._fetch_snapshots)
            for snap in snapshots:
                try:
                    self._cache.update(
                        ticker=snap.ticker,
                        price=snap.last_trade.price,
                        timestamp=snap.last_trade.timestamp / 1000.0,  # ms -> s
                    )
                except (AttributeError, TypeError) as e:
                    logger.warning("Skipping snapshot for %s: %s",
                                   getattr(snap, "ticker", "???"), e)
        except Exception as e:
            # Never crash the loop: 401 (bad key), 429 (rate limit), network errors
            logger.error("Massive poll failed: %s", e)

    def _fetch_snapshots(self) -> list:
        return self._client.get_snapshot_all(
            market_type=SnapshotMarketType.STOCKS,
            tickers=self._tickers,
        )
```

Resilience contract: a transient failure logs and retries on the next interval;
a single malformed snapshot is skipped without discarding the batch.

## 8. `factory.py` — Source Selection

The only module that reads the env var. Everything else depends on the ABC.

```python
"""Factory for creating market data sources."""

from __future__ import annotations

import logging
import os

from .cache import PriceCache
from .interface import MarketDataSource
from .massive_client import MassiveDataSource
from .simulator import SimulatorDataSource

logger = logging.getLogger(__name__)


def create_market_data_source(price_cache: PriceCache) -> MarketDataSource:
    """Return MassiveDataSource if MASSIVE_API_KEY is set, else SimulatorDataSource.

    Returns an unstarted source. Caller must await source.start(tickers).
    """
    api_key = os.environ.get("MASSIVE_API_KEY", "").strip()
    if api_key:
        logger.info("Market data source: Massive API (real data)")
        return MassiveDataSource(api_key=api_key, price_cache=price_cache)
    logger.info("Market data source: GBM Simulator")
    return SimulatorDataSource(price_cache=price_cache)
```

## 9. `stream.py` — SSE Endpoint

Streams all prices every ~500ms, but only serializes when the cache `version`
changed since the last send. Uses `EventSource`-friendly headers and a retry
directive so the browser auto-reconnects.

```python
"""SSE streaming endpoint for live price updates."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from .cache import PriceCache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stream", tags=["streaming"])


def create_stream_router(price_cache: PriceCache) -> APIRouter:
    """Create the SSE router with the price cache injected (no globals)."""

    @router.get("/prices")
    async def stream_prices(request: Request) -> StreamingResponse:
        return StreamingResponse(
            _generate_events(price_cache, request),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # disable nginx buffering if proxied
            },
        )

    return router


async def _generate_events(
    price_cache: PriceCache, request: Request, interval: float = 0.5,
) -> AsyncGenerator[str, None]:
    """Yield SSE-formatted price events; stop on client disconnect."""
    yield "retry: 1000\n\n"  # browser retries after 1s if dropped

    last_version = -1
    client_ip = request.client.host if request.client else "unknown"
    logger.info("SSE client connected: %s", client_ip)

    try:
        while True:
            if await request.is_disconnected():
                logger.info("SSE client disconnected: %s", client_ip)
                break

            if price_cache.version != last_version:
                last_version = price_cache.version
                prices = price_cache.get_all()
                if prices:
                    data = {t: u.to_dict() for t, u in prices.items()}
                    yield f"data: {json.dumps(data)}\n\n"

            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        logger.info("SSE stream cancelled for: %s", client_ip)
```

Event payload shape (one event, all tickers):

```
data: {"AAPL": {"ticker": "AAPL", "price": 190.50, "previous_price": 190.42,
       "timestamp": 1765600000.0, "change": 0.08, "change_percent": 0.042,
       "direction": "up"}, "GOOGL": {...}, ...}
```

## 10. `__init__.py` — Public API

```python
"""Market data subsystem for FinAlly."""

from .cache import PriceCache
from .factory import create_market_data_source
from .interface import MarketDataSource
from .models import PriceUpdate
from .stream import create_stream_router

__all__ = [
    "PriceUpdate",
    "PriceCache",
    "MarketDataSource",
    "create_market_data_source",
    "create_stream_router",
]
```

## 11. Wiring Into FastAPI

Create the cache and source once at startup; mount the SSE router. Use the
lifespan context so the background task starts and stops cleanly.

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.market import PriceCache, create_market_data_source, create_stream_router

DEFAULT_WATCHLIST = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA",
                     "NVDA", "META", "JPM", "V", "NFLX"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    cache = PriceCache()
    source = create_market_data_source(cache)
    await source.start(DEFAULT_WATCHLIST)

    app.state.price_cache = cache
    app.state.market_source = source
    try:
        yield
    finally:
        await source.stop()


app = FastAPI(lifespan=lifespan)


@asynccontextmanager
async def _noop():  # placeholder; router needs the cache from state
    yield


# Mount SSE — build the router after the cache exists.
# Simplest: build cache module-level, or attach in lifespan and include here.
```

A clean pattern is to build the cache/source in a small module-level singleton
so the router can be created at import time:

```python
# app/state.py
from app.market import PriceCache, create_market_data_source

price_cache = PriceCache()
market_source = create_market_data_source(price_cache)

# app/main.py
from app.state import price_cache, market_source
from app.market import create_stream_router

app.include_router(create_stream_router(price_cache))

@asynccontextmanager
async def lifespan(app):
    await market_source.start(DEFAULT_WATCHLIST)
    try:
        yield
    finally:
        await market_source.stop()
```

### Consuming prices elsewhere (portfolio, trades)

```python
from app.state import price_cache

def position_value(ticker: str, quantity: float) -> float | None:
    price = price_cache.get_price(ticker)
    return price * quantity if price is not None else None
```

### Watchlist add/remove must hit both the source and the DB

```python
async def add_to_watchlist(ticker: str):
    await market_source.add_ticker(ticker)   # start streaming it
    # ... insert into watchlist table ...

async def remove_from_watchlist(ticker: str):
    await market_source.remove_ticker(ticker)  # stop streaming + cache evict
    # ... delete from watchlist table ...
```

## 12. Testing Strategy

Unit tests live in `backend/tests/market/`. Run with `uv run --extra dev pytest`.

| Target | What to assert |
|--------|----------------|
| `models.py` | `change`/`change_percent`/`direction` for up/down/flat; zero-prev guard; `to_dict` keys |
| `cache.py` | first update sets prev==price; version increments; `remove`; thread-safety under concurrent writes |
| `simulator.py` | prices stay positive; `step()` returns all tickers; Cholesky rebuild on add/remove; correlation lookups; shock fires when `event_probability=1.0` |
| `SimulatorDataSource` | cache seeded after `start`; loop writes; `stop` cancels cleanly; add/remove reflect in cache |
| `massive_client.py` | mock `RESTClient.get_snapshot_all`; assert ms→s conversion; malformed snapshot skipped; poll failure swallowed |
| `factory.py` | key set → Massive; unset/empty/whitespace → simulator |

Example — simulator keeps prices positive and correlated draws applied:

```python
def test_step_returns_positive_prices():
    sim = GBMSimulator(["AAPL", "GOOGL"], event_probability=0.0)
    prices = sim.step()
    assert set(prices) == {"AAPL", "GOOGL"}
    assert all(p > 0 for p in prices.values())
```

Example — Massive ms→s conversion with a mocked client:

```python
def test_massive_converts_timestamp(monkeypatch):
    cache = PriceCache()
    src = MassiveDataSource("key", cache)
    fake = SimpleNamespace(ticker="AAPL",
                           last_trade=SimpleNamespace(price=190.0, timestamp=1_765_600_000_000))
    src._client = SimpleNamespace(get_snapshot_all=lambda **kw: [fake])
    src._tickers = ["AAPL"]
    asyncio.run(src._poll_once())
    upd = cache.get("AAPL")
    assert upd.price == 190.0
    assert upd.timestamp == 1_765_600_000.0
```

E2E (Playwright, `test/`): with `LLM_MOCK=true` and no `MASSIVE_API_KEY`, verify
the default watchlist streams prices, prices flash on change, and the SSE
connection reconnects after a drop.

## 13. Design Decisions Recap

| Decision | Rationale |
|----------|-----------|
| ABC + factory | Swap source via env var; consumers untouched |
| Cache as the seam | Producers/consumers decoupled; multi-user ready |
| `version` counter | O(1) SSE change detection, no per-ticker diff |
| Push into cache (not pull) | One model for 500ms sim and 15s REST poll |
| Single snapshot call | All tickers in one request → free-tier safe |
| `asyncio.to_thread` for Massive | Sync client never blocks the event loop |
| GBM + Cholesky | Realistic, positive, sector-correlated prices |
| Broad try/except in pollers | Transient API errors never crash the app |
| Split GBMSimulator vs DataSource | Math unit-tested without asyncio |
```

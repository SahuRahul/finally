# Massive API (formerly Polygon.io) — Reference

Research notes and code examples for retrieving real-time and end-of-day (EOD)
stock prices for multiple tickers. This is the source-of-truth research that
drives the design in [MARKET_INTERFACE.md](MARKET_INTERFACE.md).

## Background

Polygon.io rebranded to **Massive** (massive.com) on 2025-10-30. Existing API
keys, accounts, and integrations continue to work unchanged.

- New API base: `https://api.massive.com`
- Legacy base `https://api.polygon.io` is still supported for an extended period
- Official Python client: `massive` (GitHub: `massive-com/client-python`),
  requires Python >= 3.9
- The client is a drop-in successor to the old `polygon-api-client` package

In this project the key is read from the `MASSIVE_API_KEY` environment variable.
If it is unset or empty, the project uses the built-in simulator instead (see
[MARKET_SIMULATOR.md](MARKET_SIMULATOR.md)).

## Python Client

```bash
uv add massive
```

```python
from massive import RESTClient

client = RESTClient(api_key="<MASSIVE_API_KEY>")
```

The `RESTClient` is **synchronous** (blocking HTTP under the hood). In an async
app it must be called from a worker thread (`asyncio.to_thread(...)`) so it does
not block the event loop. This is exactly how the project's `MassiveDataSource`
uses it.

## Rate Limits

| Tier | Limit | Recommended poll interval |
|------|-------|---------------------------|
| Free | 5 requests/minute | 15 seconds |
| Starter / paid | higher | 2-5 seconds |

The key design consequence: **fetch all watched tickers in a single request**
(the full snapshot endpoint), not one request per ticker. Ten tickers polled
individually would blow the free-tier budget instantly; one snapshot call covers
all of them.

## Endpoints Used By This Project

### 1. Full Market Snapshot — primary real-time source

Fetch the latest snapshot for many tickers in one call. This is what the live
poller uses.

REST:
```
GET /v2/snapshot/locale/us/markets/stocks/tickers?tickers=AAPL,GOOGL,MSFT
```

Python client:
```python
from massive.rest.models import SnapshotMarketType

snapshots = client.get_snapshot_all(
    market_type=SnapshotMarketType.STOCKS,
    tickers=["AAPL", "GOOGL", "MSFT"],
)

for snap in snapshots:
    print(snap.ticker, snap.last_trade.price, snap.last_trade.timestamp)
```

Key snapshot object attributes:

| Attribute | Meaning |
|-----------|---------|
| `snap.ticker` | Ticker symbol |
| `snap.last_trade.price` | Most recent trade price |
| `snap.last_trade.timestamp` | Unix **milliseconds** (divide by 1000 for seconds) |
| `snap.last_quote` | Latest bid/ask |
| `snap.day` | Today's aggregate (OHLCV) |
| `snap.prev_day` | Previous trading day's aggregate (OHLCV) — used for daily % change |
| `snap.todays_change` / `snap.todays_change_percent` | Convenience fields |

Notes:
- Snapshot data is cleared daily ~3:30 AM EST and repopulates from ~4:00 AM EST.
- Outside market hours `last_trade` reflects the last trade of the prior
  session; `prev_day` is the reference for daily change.

### 2. Single Ticker Snapshot

```python
snap = client.get_snapshot_ticker(market_type=SnapshotMarketType.STOCKS, ticker="AAPL")
price = snap.last_trade.price
```

Useful for validating a ticker exists when the user adds one to the watchlist.

### 3. Previous Close — simple EOD price

```python
agg = client.get_previous_close_agg(ticker="AAPL")
# agg[0].close, agg[0].open, agg[0].high, agg[0].low, agg[0].volume
```

REST: `GET /v2/aggs/ticker/{ticker}/prev`

### 4. Daily Open/Close — EOD for a specific date

```python
daily = client.get_daily_open_close_agg(ticker="AAPL", date="2026-06-12")
# daily.open, daily.close, daily.high, daily.low, daily.volume
```

REST: `GET /v1/open-close/{ticker}/{date}`

### 5. Aggregate Bars — historical series (charts / sparklines backfill)

```python
bars = []
for bar in client.list_aggs(
    ticker="AAPL",
    multiplier=1,
    timespan="day",        # "minute" | "hour" | "day" ...
    from_="2026-01-01",
    to="2026-06-13",
    limit=50000,
):
    bars.append(bar)       # bar.open, bar.high, bar.low, bar.close, bar.volume, bar.timestamp
```

REST: `GET /v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from}/{to}`

The client auto-paginates iterator endpoints (`list_aggs`, `list_trades`,
`list_quotes`); `limit` is page size, not a total cap.

## Error Handling

The poller must not crash the app on transient API failures. Common cases:

| Failure | Cause | Handling |
|---------|-------|----------|
| 401 | bad/expired key | log, keep retrying (config issue, surfaced in logs) |
| 429 | rate limit exceeded | log, retry on next interval (increase interval) |
| Network / timeout | connectivity | log, retry on next interval |
| Missing fields on a snapshot | thin/halted ticker | skip that ticker, process the rest |

Strategy: wrap each poll in a broad `try/except`, log the error, and let the
loop retry on the next tick. Per-snapshot parsing is wrapped separately so one
malformed entry does not discard the whole batch.

## Mapping To The Project's Cache

Each successful snapshot becomes a `cache.update(ticker, price, timestamp)` call.
The `PriceCache` computes `previous_price`, `change`, and `direction`. Timestamps
are converted from Massive's milliseconds to seconds:

```python
self._cache.update(
    ticker=snap.ticker,
    price=snap.last_trade.price,
    timestamp=snap.last_trade.timestamp / 1000.0,
)
```

## Sources

- [Massive Python client (GitHub)](https://github.com/massive-com/client-python)
- [Massive Stocks REST API overview](https://massive.com/docs/rest/stocks/overview)
- [Massive + Python guide](https://massive.com/blog/polygon-io-with-python-for-stock-market-data)
- [Massive home / rebrand](https://massive.com/)

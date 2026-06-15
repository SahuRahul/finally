"""Watchlist operations that keep the DB and market data source in sync.

Adding a ticker both persists it and registers it with the running market
data source so prices begin streaming. Removing does the reverse and clears
the price cache entry. Shared by the REST API and LLM chat flows.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool

from app import db


def _tickers() -> list[str]:
    """Watchlist tickers in added order."""
    return [row["ticker"] for row in db.get_watchlist()]


async def add_to_watchlist(app: FastAPI, ticker: str) -> bool:
    """Add a ticker to the watchlist and start streaming its price.

    Returns False if the ticker was already present.
    """
    ticker = ticker.strip().upper()
    if ticker in await run_in_threadpool(_tickers):
        return False
    await run_in_threadpool(db.add_watchlist, ticker)
    await app.state.market_source.add_ticker(ticker)
    return True


async def remove_from_watchlist(app: FastAPI, ticker: str) -> bool:
    """Remove a ticker from the watchlist and stop tracking its price.

    Returns False if the ticker was not present.
    """
    ticker = ticker.strip().upper()
    if ticker not in await run_in_threadpool(_tickers):
        return False
    await run_in_threadpool(db.remove_watchlist, ticker)
    await app.state.market_source.remove_ticker(ticker)
    return True


def build_watchlist(app: FastAPI) -> list[dict]:
    """Current watchlist tickers enriched with the latest cached price."""
    cache = app.state.price_cache
    items: list[dict] = []
    for ticker in _tickers():
        update = cache.get(ticker)
        if update:
            items.append(
                {
                    "ticker": ticker,
                    "price": update.price,
                    "previous_price": update.previous_price,
                    "change": update.change,
                    "change_percent": update.change_percent,
                    "direction": update.direction,
                }
            )
        else:
            items.append(
                {
                    "ticker": ticker,
                    "price": None,
                    "previous_price": None,
                    "change": None,
                    "change_percent": None,
                    "direction": None,
                }
            )
    return items

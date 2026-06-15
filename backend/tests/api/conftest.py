"""Fixtures for portfolio service and API tests: isolated DB + seeded cache."""

import pytest

from app.market.cache import PriceCache


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Point the DB at a fresh temp file so each test starts clean and seeded."""
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("FINALLY_DB_PATH", str(db_file))
    # First access triggers lazy init + seed.
    from app import db

    db.get_profile()
    return db_file


@pytest.fixture
def cache():
    """A PriceCache seeded with prices for the default watchlist tickers."""
    c = PriceCache()
    prices = {
        "AAPL": 190.0,
        "GOOGL": 175.0,
        "MSFT": 420.0,
        "AMZN": 185.0,
        "TSLA": 250.0,
        "NVDA": 120.0,
        "META": 500.0,
        "JPM": 200.0,
        "V": 280.0,
        "NFLX": 650.0,
    }
    for ticker, price in prices.items():
        c.update(ticker, price)
    return c

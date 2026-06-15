"""Fixtures for LLM tests: isolated seeded DB, populated price cache, mock mode."""

import pytest

from app.market import PriceCache


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    """Point the DB at a fresh temp file so each test gets a clean seeded DB."""
    path = tmp_path / "test.db"
    monkeypatch.setenv("FINALLY_DB_PATH", str(path))
    return path


@pytest.fixture
def cache():
    """A price cache seeded with prices for the default watchlist."""
    c = PriceCache()
    seed = {
        "AAPL": 190.0, "GOOGL": 175.0, "MSFT": 420.0, "AMZN": 185.0,
        "TSLA": 250.0, "NVDA": 120.0, "META": 500.0, "JPM": 200.0,
        "V": 280.0, "NFLX": 650.0, "PYPL": 70.0,
    }
    for ticker, price in seed.items():
        c.update(ticker, price)
    return c


@pytest.fixture
def mock_mode(monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "true")

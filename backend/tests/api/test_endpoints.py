"""API endpoint shapes and error codes."""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client(temp_db):
    """TestClient with lifespan run; seed deterministic prices into the cache."""
    app = create_app()
    with TestClient(app) as c:
        cache = app.state.price_cache
        for ticker, price in {
            "AAPL": 190.0,
            "GOOGL": 175.0,
            "MSFT": 420.0,
            "TSLA": 250.0,
        }.items():
            cache.update(ticker, price)
        yield c


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_openapi_schema_builds(client):
    """Regression: streaming route annotations must not break OpenAPI/docs."""
    r = client.get("/openapi.json")
    assert r.status_code == 200
    assert "/api/stream/prices" in r.json()["paths"]


def test_get_portfolio_initial(client):
    r = client.get("/api/portfolio")
    assert r.status_code == 200
    body = r.json()
    assert body["cash_balance"] == 10000.0
    assert body["positions"] == []
    assert set(body) == {
        "cash_balance",
        "positions",
        "positions_value",
        "total_value",
        "total_unrealized_pnl",
    }


def test_trade_buy_and_portfolio_updates(client):
    r = client.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 10, "side": "buy"})
    assert r.status_code == 200
    body = r.json()
    assert body["trade"]["ticker"] == "AAPL"
    assert body["trade"]["side"] == "buy"
    assert body["portfolio"]["cash_balance"] == pytest.approx(10000.0 - 1900.0)
    assert body["portfolio"]["positions"][0]["ticker"] == "AAPL"


def test_trade_lowercase_ticker_normalized(client):
    r = client.post("/api/portfolio/trade", json={"ticker": "aapl", "quantity": 1, "side": "buy"})
    assert r.status_code == 200
    assert r.json()["trade"]["ticker"] == "AAPL"


def test_trade_insufficient_cash_returns_400(client):
    r = client.post("/api/portfolio/trade", json={"ticker": "MSFT", "quantity": 100, "side": "buy"})
    assert r.status_code == 400
    assert "Insufficient cash" in r.json()["detail"]


def test_trade_invalid_quantity_returns_422(client):
    r = client.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 0, "side": "buy"})
    assert r.status_code == 422


def test_history_grows_after_trade(client):
    client.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 1, "side": "buy"})
    r = client.get("/api/portfolio/history")
    assert r.status_code == 200
    history = r.json()
    assert len(history) >= 1
    assert set(history[0]) == {"total_value", "recorded_at"}


def test_get_watchlist_seeded(client):
    r = client.get("/api/watchlist")
    assert r.status_code == 200
    items = r.json()
    tickers = [i["ticker"] for i in items]
    assert "AAPL" in tickers
    assert len(tickers) == 10
    aapl = next(i for i in items if i["ticker"] == "AAPL")
    assert aapl["price"] == 190.0
    assert aapl["direction"] in {"up", "down", "flat"}


def test_add_watchlist(client):
    r = client.post("/api/watchlist", json={"ticker": "PYPL"})
    assert r.status_code == 200
    assert "PYPL" in [i["ticker"] for i in r.json()]


def test_add_duplicate_watchlist_returns_409(client):
    r = client.post("/api/watchlist", json={"ticker": "AAPL"})
    assert r.status_code == 409


def test_remove_watchlist(client):
    r = client.delete("/api/watchlist/AAPL")
    assert r.status_code == 200
    assert "AAPL" not in [i["ticker"] for i in r.json()]


def test_remove_unknown_watchlist_returns_404(client):
    r = client.delete("/api/watchlist/ZZZZ")
    assert r.status_code == 404

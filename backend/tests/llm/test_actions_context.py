"""Direct tests for the local executors and context builder."""

from app.db import get_positions, get_profile
from app.llm.actions import execute_trade, execute_watchlist_change
from app.llm.context import build_portfolio_context
from app.llm.schema import TradeRequest, WatchlistChange


def test_buy_then_sell_round_trip(db_path, cache):
    buy = execute_trade(TradeRequest(ticker="aapl", side="buy", quantity=4), cache)
    assert buy["status"] == "executed"
    assert buy["ticker"] == "AAPL"  # uppercased
    assert {p["ticker"] for p in get_positions()} == {"AAPL"}

    sell = execute_trade(TradeRequest(ticker="AAPL", side="sell", quantity=4), cache)
    assert sell["status"] == "executed"
    # Selling the full position removes it; cash returns to start.
    assert get_positions() == []
    assert get_profile()["cash_balance"] == 10000.0


def test_buy_averages_cost(db_path, cache):
    execute_trade(TradeRequest(ticker="AAPL", side="buy", quantity=2), cache)
    cache.update("AAPL", 200.0)  # price moves up
    execute_trade(TradeRequest(ticker="AAPL", side="buy", quantity=2), cache)
    pos = {p["ticker"]: p for p in get_positions()}["AAPL"]
    assert pos["quantity"] == 4
    assert pos["avg_cost"] == (190.0 * 2 + 200.0 * 2) / 4


def test_trade_no_price_errors(db_path, cache):
    result = execute_trade(TradeRequest(ticker="ZZZZ", side="buy", quantity=1), cache)
    assert result["status"] == "error"
    assert "No live price" in result["error"]


def test_watchlist_add_remove(db_path):
    add = execute_watchlist_change(WatchlistChange(ticker="pypl", action="add"))
    assert add["ticker"] == "PYPL"
    assert add["action"] == "add"
    remove = execute_watchlist_change(WatchlistChange(ticker="PYPL", action="remove"))
    assert remove["action"] == "remove"


def test_context_includes_cash_positions_watchlist(db_path, cache):
    execute_trade(TradeRequest(ticker="AAPL", side="buy", quantity=3), cache)
    ctx = build_portfolio_context(cache)
    assert "Cash balance:" in ctx
    assert "AAPL" in ctx
    assert "Total portfolio value:" in ctx
    assert "Watchlist:" in ctx
    assert "unrealized P&L" in ctx

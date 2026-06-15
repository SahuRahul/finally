"""Trade execution math and portfolio valuation."""

import pytest

from app import db
from app.portfolio_service import TradeError, build_portfolio, execute_trade


def test_empty_portfolio_is_all_cash(temp_db, cache):
    p = build_portfolio(cache)
    assert p.cash_balance == 10000.0
    assert p.positions == []
    assert p.total_value == 10000.0
    assert p.total_unrealized_pnl == 0.0


def test_buy_reduces_cash_and_creates_position(temp_db, cache):
    result = execute_trade(cache, "AAPL", 10, "buy")
    assert result.trade.ticker == "AAPL"
    assert result.trade.price == 190.0
    p = result.portfolio
    assert p.cash_balance == pytest.approx(10000.0 - 1900.0)
    assert len(p.positions) == 1
    pos = p.positions[0]
    assert pos.quantity == 10
    assert pos.avg_cost == 190.0
    assert pos.current_price == 190.0
    assert pos.unrealized_pnl == 0.0


def test_buy_twice_averages_cost(temp_db, cache):
    execute_trade(cache, "AAPL", 10, "buy")  # 10 @ 190
    cache.update("AAPL", 210.0)
    result = execute_trade(cache, "AAPL", 10, "buy")  # 10 @ 210
    pos = result.portfolio.positions[0]
    assert pos.quantity == 20
    assert pos.avg_cost == pytest.approx(200.0)


def test_sell_increases_cash_and_realizes(temp_db, cache):
    execute_trade(cache, "AAPL", 10, "buy")  # spend 1900
    cache.update("AAPL", 200.0)
    result = execute_trade(cache, "AAPL", 5, "sell")  # +1000
    p = result.portfolio
    assert p.cash_balance == pytest.approx(10000.0 - 1900.0 + 1000.0)
    assert p.positions[0].quantity == 5


def test_full_sell_removes_position(temp_db, cache):
    execute_trade(cache, "AAPL", 10, "buy")
    result = execute_trade(cache, "AAPL", 10, "sell")
    assert result.portfolio.positions == []
    assert db.get_positions() == []


def test_buy_insufficient_cash_raises(temp_db, cache):
    with pytest.raises(TradeError, match="Insufficient cash"):
        execute_trade(cache, "MSFT", 100, "buy")  # 100 * 420 = 42000 > 10000


def test_sell_more_than_owned_raises(temp_db, cache):
    execute_trade(cache, "AAPL", 5, "buy")
    with pytest.raises(TradeError, match="Insufficient shares"):
        execute_trade(cache, "AAPL", 10, "sell")


def test_trade_unknown_price_raises(temp_db, cache):
    with pytest.raises(TradeError, match="No live price"):
        execute_trade(cache, "UNKN", 1, "buy")


def test_unrealized_pnl_tracks_price(temp_db, cache):
    execute_trade(cache, "AAPL", 10, "buy")  # cost basis 1900
    cache.update("AAPL", 200.0)
    p = build_portfolio(cache)
    pos = p.positions[0]
    assert pos.unrealized_pnl == pytest.approx(100.0)
    assert pos.unrealized_pnl_percent == pytest.approx(5.26, abs=0.01)
    assert p.total_unrealized_pnl == pytest.approx(100.0)


def test_snapshot_recorded_on_trade(temp_db, cache):
    execute_trade(cache, "AAPL", 1, "buy")
    snaps = db.get_snapshots()
    assert len(snaps) == 1

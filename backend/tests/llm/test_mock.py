"""Mock-response pattern-matching tests."""

from app.llm.mock import mock_response


def test_buy_pattern():
    r = mock_response("Please buy 10 AAPL now")
    assert len(r.trades) == 1
    assert r.trades[0].side == "buy"
    assert r.trades[0].ticker == "AAPL"
    assert r.trades[0].quantity == 10
    assert not r.watchlist_changes


def test_sell_pattern_fractional():
    r = mock_response("sell 2.5 TSLA")
    assert r.trades[0].side == "sell"
    assert r.trades[0].ticker == "TSLA"
    assert r.trades[0].quantity == 2.5


def test_add_watchlist_pattern():
    r = mock_response("add PYPL to watchlist")
    assert len(r.watchlist_changes) == 1
    assert r.watchlist_changes[0].action == "add"
    assert r.watchlist_changes[0].ticker == "PYPL"
    assert not r.trades


def test_remove_watchlist_pattern():
    r = mock_response("remove NFLX")
    assert r.watchlist_changes[0].action == "remove"
    assert r.watchlist_changes[0].ticker == "NFLX"


def test_plain_chat_no_actions():
    r = mock_response("how is my portfolio doing?")
    assert r.message
    assert not r.trades
    assert not r.watchlist_changes

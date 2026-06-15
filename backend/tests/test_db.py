"""Unit tests for the database layer."""

import pytest

from app import db
from app.db.connection import DEFAULT_WATCHLIST


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    """Point the data layer at a fresh temporary database for each test."""
    monkeypatch.setenv("FINALLY_DB_PATH", str(tmp_path / "test.db"))


# --- Init / seed -----------------------------------------------------------

def test_seed_creates_profile_and_watchlist():
    profile = db.get_profile()
    assert profile["id"] == "default"
    assert profile["cash_balance"] == 10000.0
    tickers = [w["ticker"] for w in db.get_watchlist()]
    assert tickers == DEFAULT_WATCHLIST


def test_init_is_idempotent():
    db.get_profile()
    cash_before = db.get_profile()["cash_balance"]
    db.update_cash(5000.0)
    # A subsequent connection must not re-seed and reset the data.
    assert db.get_profile()["cash_balance"] == 5000.0
    assert cash_before == 10000.0
    assert len(db.get_watchlist()) == len(DEFAULT_WATCHLIST)


# --- Profile ---------------------------------------------------------------

def test_update_cash():
    db.update_cash(1234.56)
    assert db.get_profile()["cash_balance"] == 1234.56


# --- Watchlist -------------------------------------------------------------

def test_add_and_remove_watchlist():
    db.add_watchlist("PYPL")
    assert "PYPL" in [w["ticker"] for w in db.get_watchlist()]
    db.remove_watchlist("PYPL")
    assert "PYPL" not in [w["ticker"] for w in db.get_watchlist()]


def test_add_watchlist_is_idempotent():
    count = len(db.get_watchlist())
    db.add_watchlist("AAPL")  # already seeded
    assert len(db.get_watchlist()) == count


# --- Positions -------------------------------------------------------------

def test_upsert_position_insert_and_update():
    db.upsert_position("AAPL", 10, 190.0)
    pos = db.get_positions()
    assert len(pos) == 1
    assert pos[0]["quantity"] == 10
    db.upsert_position("AAPL", 15, 192.0)
    pos = db.get_positions()
    assert len(pos) == 1
    assert pos[0]["quantity"] == 15
    assert pos[0]["avg_cost"] == 192.0


def test_upsert_position_zero_removes():
    db.upsert_position("TSLA", 5, 200.0)
    db.upsert_position("TSLA", 0, 0.0)
    assert db.get_positions() == []


def test_get_position_and_delete():
    assert db.get_position("NVDA") is None
    db.upsert_position("NVDA", 3, 500.0)
    assert db.get_position("NVDA")["quantity"] == 3
    db.delete_position("NVDA")
    assert db.get_position("NVDA") is None


def test_init_db_seeds_and_is_repeatable():
    db.init_db()
    db.init_db()
    assert db.get_profile()["cash_balance"] == 10000.0


# --- Trades ----------------------------------------------------------------

def test_record_and_get_trades():
    db.record_trade("AAPL", "buy", 10, 190.0)
    db.record_trade("AAPL", "sell", 5, 195.0)
    trades = db.get_trades()
    assert len(trades) == 2
    # Most recent first
    assert trades[0]["side"] == "sell"
    assert db.get_trades(limit=1)[0]["side"] == "sell"


# --- Snapshots -------------------------------------------------------------

def test_record_and_get_snapshots():
    db.record_snapshot(10000.0)
    db.record_snapshot(10500.0)
    snaps = db.get_snapshots()
    assert [s["total_value"] for s in snaps] == [10000.0, 10500.0]


# --- Chat messages ---------------------------------------------------------

def test_add_and_get_chat_messages():
    db.add_chat_message("user", "hello")
    db.add_chat_message("assistant", "hi", actions={"trades": [{"ticker": "AAPL"}]})
    msgs = db.get_chat_messages()
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[0]["actions"] is None
    assert msgs[1]["actions"] == {"trades": [{"ticker": "AAPL"}]}

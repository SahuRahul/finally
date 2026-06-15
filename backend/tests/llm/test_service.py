"""End-to-end chat service tests (mock mode, isolated DB)."""

from app.db import get_chat_messages, get_positions, get_profile, get_watchlist
from app.llm.service import generate_chat_response


def test_plain_chat_no_actions(db_path, cache, mock_mode):
    result = generate_chat_response("how is my portfolio?", cache)
    assert result["message"]
    assert result["actions"] == []
    # Persisted: one user + one assistant message.
    msgs = get_chat_messages()
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert msgs[1]["actions"] is None


def test_chat_executes_buy(db_path, cache, mock_mode):
    result = generate_chat_response("buy 5 AAPL", cache)
    assert len(result["actions"]) == 1
    action = result["actions"][0]
    assert action["status"] == "executed"
    assert action["ticker"] == "AAPL"
    assert action["side"] == "buy"
    assert action["price"] == 190.0

    # Position and cash updated.
    positions = {p["ticker"]: p for p in get_positions()}
    assert positions["AAPL"]["quantity"] == 5
    assert get_profile()["cash_balance"] == 10000.0 - 5 * 190.0

    # Assistant message stored the executed action.
    assistant = get_chat_messages()[-1]
    assert assistant["actions"][0]["status"] == "executed"


def test_chat_buy_insufficient_cash_returns_error(db_path, cache, mock_mode):
    # 1000 shares of AAPL @ 190 = 190k, well over the 10k balance.
    result = generate_chat_response("buy 1000 AAPL", cache)
    action = result["actions"][0]
    assert action["status"] == "error"
    assert "Insufficient cash" in action["error"]
    # No position created, cash unchanged.
    assert get_positions() == []
    assert get_profile()["cash_balance"] == 10000.0


def test_chat_sell_more_than_owned_returns_error(db_path, cache, mock_mode):
    generate_chat_response("buy 2 TSLA", cache)
    result = generate_chat_response("sell 10 TSLA", cache)
    action = result["actions"][0]
    assert action["status"] == "error"
    assert "Insufficient shares" in action["error"]


def test_chat_adds_watchlist_ticker(db_path, cache, mock_mode):
    # PYPL is not in the default seed watchlist.
    assert "PYPL" not in {w["ticker"] for w in get_watchlist()}
    result = generate_chat_response("add PYPL to watchlist", cache)
    action = result["actions"][0]
    assert action == {
        "type": "watchlist",
        "status": "executed",
        "ticker": "PYPL",
        "action": "add",
    }
    assert "PYPL" in {w["ticker"] for w in get_watchlist()}


def test_chat_removes_watchlist_ticker(db_path, cache, mock_mode):
    assert "NFLX" in {w["ticker"] for w in get_watchlist()}
    generate_chat_response("remove NFLX", cache)
    assert "NFLX" not in {w["ticker"] for w in get_watchlist()}


def test_history_is_loaded_and_grows(db_path, cache, mock_mode):
    generate_chat_response("hello", cache)
    generate_chat_response("how about now?", cache)
    msgs = get_chat_messages()
    # 2 turns -> 4 messages, oldest first.
    assert len(msgs) == 4
    assert msgs[0]["content"] == "hello"


def test_injected_executor_is_used(db_path, cache, mock_mode):
    calls = []

    class FakeExecutor:
        def trade(self, trade, cache, user_id):
            calls.append(("trade", trade.ticker))
            return {"type": "trade", "status": "executed", "ticker": trade.ticker}

        def watchlist(self, change, user_id):
            calls.append(("watchlist", change.ticker))
            return {"type": "watchlist", "status": "executed", "ticker": change.ticker}

    generate_chat_response("buy 5 AAPL", cache, executor=FakeExecutor())
    assert calls == [("trade", "AAPL")]
    # The fake executor ran instead of touching the DB.
    assert get_positions() == []

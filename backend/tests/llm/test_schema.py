"""Structured-output schema parsing tests."""

import pytest
from pydantic import ValidationError

from app.llm.schema import ChatResponse


def test_minimal_message_only():
    r = ChatResponse.model_validate({"message": "hello"})
    assert r.message == "hello"
    assert r.trades == []
    assert r.watchlist_changes == []


def test_full_schema():
    r = ChatResponse.model_validate(
        {
            "message": "Done.",
            "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 10}],
            "watchlist_changes": [{"ticker": "PYPL", "action": "add"}],
        }
    )
    assert r.trades[0].ticker == "AAPL"
    assert r.trades[0].side == "buy"
    assert r.watchlist_changes[0].action == "add"


def test_invalid_side_rejected():
    with pytest.raises(ValidationError):
        ChatResponse.model_validate(
            {"message": "x", "trades": [{"ticker": "AAPL", "side": "hold", "quantity": 1}]}
        )


def test_nonpositive_quantity_rejected():
    with pytest.raises(ValidationError):
        ChatResponse.model_validate(
            {"message": "x", "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 0}]}
        )


def test_missing_message_rejected():
    with pytest.raises(ValidationError):
        ChatResponse.model_validate({"trades": []})

"""Structured-output schema for the chat assistant.

The LLM responds with JSON matching ChatResponse (PLAN.md section 9):

    {
      "message": "...",
      "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 10}],
      "watchlist_changes": [{"ticker": "PYPL", "action": "add"}]
    }
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TradeRequest(BaseModel):
    """A trade the assistant wants to execute."""

    ticker: str
    side: Literal["buy", "sell"]
    quantity: float = Field(gt=0)


class WatchlistChange(BaseModel):
    """A watchlist modification the assistant wants to make."""

    ticker: str
    action: Literal["add", "remove"]


class ChatResponse(BaseModel):
    """Structured response returned by the LLM."""

    message: str
    trades: list[TradeRequest] = Field(default_factory=list)
    watchlist_changes: list[WatchlistChange] = Field(default_factory=list)

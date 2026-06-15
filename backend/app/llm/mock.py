"""Deterministic mock LLM responses for LLM_MOCK=true (tests, CI, no API key).

Responses are pattern-matched on the user's message so E2E/integration tests
can deterministically drive a trade, a watchlist change, or plain chat.

Test triggers (case-insensitive substring match):
- "buy <QTY> <TICKER>"        -> a buy trade for that ticker/quantity
- "sell <QTY> <TICKER>"       -> a sell trade for that ticker/quantity
- "add <TICKER> to watchlist" -> add the ticker to the watchlist
- "remove <TICKER>"           -> remove the ticker from the watchlist
- anything else               -> a plain analytical reply, no actions
"""

from __future__ import annotations

import re

from .schema import ChatResponse, TradeRequest, WatchlistChange

_BUY = re.compile(r"\bbuy\s+(\d+(?:\.\d+)?)\s+([A-Za-z]{1,5})\b", re.IGNORECASE)
_SELL = re.compile(r"\bsell\s+(\d+(?:\.\d+)?)\s+([A-Za-z]{1,5})\b", re.IGNORECASE)
_ADD = re.compile(r"\badd\s+([A-Za-z]{1,5})\s+to\s+watchlist\b", re.IGNORECASE)
_REMOVE = re.compile(r"\bremove\s+([A-Za-z]{1,5})\b", re.IGNORECASE)


def mock_response(user_message: str) -> ChatResponse:
    """Return a deterministic ChatResponse based on the user's message."""
    buy = _BUY.search(user_message)
    if buy:
        qty, ticker = float(buy.group(1)), buy.group(2).upper()
        return ChatResponse(
            message=f"Buying {qty:g} shares of {ticker}.",
            trades=[TradeRequest(ticker=ticker, side="buy", quantity=qty)],
        )

    sell = _SELL.search(user_message)
    if sell:
        qty, ticker = float(sell.group(1)), sell.group(2).upper()
        return ChatResponse(
            message=f"Selling {qty:g} shares of {ticker}.",
            trades=[TradeRequest(ticker=ticker, side="sell", quantity=qty)],
        )

    add = _ADD.search(user_message)
    if add:
        ticker = add.group(1).upper()
        return ChatResponse(
            message=f"Added {ticker} to your watchlist.",
            watchlist_changes=[WatchlistChange(ticker=ticker, action="add")],
        )

    remove = _REMOVE.search(user_message)
    if remove:
        ticker = remove.group(1).upper()
        return ChatResponse(
            message=f"Removed {ticker} from your watchlist.",
            watchlist_changes=[WatchlistChange(ticker=ticker, action="remove")],
        )

    return ChatResponse(
        message=(
            "Here is a summary of your portfolio. Ask me to buy or sell shares, "
            "or to add or remove tickers from your watchlist."
        )
    )

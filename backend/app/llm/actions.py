"""Auto-execute trades and watchlist changes requested by the assistant.

Trades go through the same validation as manual trades: sufficient cash for
buys, sufficient shares for sells, instant fill at the current cache price.
Failures are returned as error strings (not raised) so the chat flow can pass
them back to the LLM/user.
"""

from __future__ import annotations

from app.db import (
    add_watchlist,
    get_positions,
    get_profile,
    record_snapshot,
    record_trade,
    remove_watchlist,
    update_cash,
    upsert_position,
)
from app.market import PriceCache

from .schema import TradeRequest, WatchlistChange


def _portfolio_total(cache: PriceCache, user_id: str) -> float:
    """Cash plus mark-to-market value of all positions."""
    cash = get_profile(user_id)["cash_balance"]
    total = cash
    for p in get_positions(user_id):
        price = cache.get_price(p["ticker"])
        if price is not None:
            total += p["quantity"] * price
    return total


def execute_trade(
    trade: TradeRequest, cache: PriceCache, user_id: str = "default"
) -> dict:
    """Execute one trade. Returns an action dict with status 'executed' or 'error'.

    On success the position, cash, and a portfolio snapshot are all updated.
    """
    ticker = trade.ticker.upper()
    side = trade.side
    quantity = trade.quantity

    price = cache.get_price(ticker)
    if price is None:
        return _error(ticker, side, quantity, f"No live price available for {ticker}.")

    positions = {p["ticker"]: p for p in get_positions(user_id)}
    cash = get_profile(user_id)["cash_balance"]

    if side == "buy":
        cost = price * quantity
        if cost > cash:
            return _error(
                ticker, side, quantity,
                f"Insufficient cash: need ${cost:,.2f}, have ${cash:,.2f}.",
            )
        existing = positions.get(ticker)
        if existing:
            new_qty = existing["quantity"] + quantity
            new_avg = (
                existing["avg_cost"] * existing["quantity"] + price * quantity
            ) / new_qty
        else:
            new_qty, new_avg = quantity, price
        update_cash(cash - cost, user_id)
        upsert_position(ticker, new_qty, new_avg, user_id)
    else:  # sell
        existing = positions.get(ticker)
        owned = existing["quantity"] if existing else 0.0
        if quantity > owned:
            return _error(
                ticker, side, quantity,
                f"Insufficient shares: trying to sell {quantity:g}, own {owned:g}.",
            )
        proceeds = price * quantity
        new_qty = owned - quantity
        update_cash(cash + proceeds, user_id)
        # avg_cost is preserved on partial sells; 0 qty removes the position.
        upsert_position(ticker, new_qty, existing["avg_cost"] if existing else price, user_id)

    record_trade(ticker, side, quantity, price, user_id)
    record_snapshot(_portfolio_total(cache, user_id), user_id)

    return {
        "type": "trade",
        "status": "executed",
        "ticker": ticker,
        "side": side,
        "quantity": quantity,
        "price": price,
    }


def execute_watchlist_change(
    change: WatchlistChange, user_id: str = "default"
) -> dict:
    """Add or remove a watchlist ticker. Returns an action dict."""
    ticker = change.ticker.upper()
    if change.action == "add":
        add_watchlist(ticker, user_id)
    else:
        remove_watchlist(ticker, user_id)
    return {
        "type": "watchlist",
        "status": "executed",
        "ticker": ticker,
        "action": change.action,
    }


def _error(ticker: str, side: str, quantity: float, message: str) -> dict:
    return {
        "type": "trade",
        "status": "error",
        "ticker": ticker,
        "side": side,
        "quantity": quantity,
        "error": message,
    }

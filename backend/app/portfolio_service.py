"""Portfolio valuation and trade execution.

This module owns the trade math and portfolio valuation reused by both the
REST API (POST /api/portfolio/trade) and the LLM chat auto-execution flow.

Pricing comes from the shared PriceCache; persistence goes through the db
data-access layer. All functions are synchronous; callers in async contexts
should wrap them in run_in_threadpool.
"""

from __future__ import annotations

from app import db
from app.market.cache import PriceCache
from app.schemas import (
    PortfolioOut,
    PositionOut,
    TradeOut,
    TradeResult,
)


class TradeError(Exception):
    """Raised when a trade fails validation (insufficient cash/shares, no price)."""


def _price_for(cache: PriceCache, ticker: str) -> float:
    """Latest cached price for a ticker, or raise TradeError if unavailable."""
    price = cache.get_price(ticker)
    if price is None:
        raise TradeError(f"No live price available for {ticker}")
    return price


def build_portfolio(cache: PriceCache, user_id: str = "default") -> PortfolioOut:
    """Compute the full portfolio snapshot from stored positions and live prices.

    Positions with no cached price fall back to avg_cost so valuation stays sane
    before the first price tick arrives.
    """
    profile = db.get_profile(user_id)
    cash = profile["cash_balance"]

    positions: list[PositionOut] = []
    positions_value = 0.0
    total_pnl = 0.0

    for row in db.get_positions(user_id):
        qty = row["quantity"]
        avg_cost = row["avg_cost"]
        current_price = cache.get_price(row["ticker"])
        if current_price is None:
            current_price = avg_cost

        market_value = qty * current_price
        cost_basis = qty * avg_cost
        pnl = market_value - cost_basis
        pnl_pct = (pnl / cost_basis * 100) if cost_basis else 0.0

        positions.append(
            PositionOut(
                ticker=row["ticker"],
                quantity=round(qty, 6),
                avg_cost=round(avg_cost, 2),
                current_price=round(current_price, 2),
                market_value=round(market_value, 2),
                unrealized_pnl=round(pnl, 2),
                unrealized_pnl_percent=round(pnl_pct, 2),
            )
        )
        positions_value += market_value
        total_pnl += pnl

    return PortfolioOut(
        cash_balance=round(cash, 2),
        positions=positions,
        positions_value=round(positions_value, 2),
        total_value=round(cash + positions_value, 2),
        total_unrealized_pnl=round(total_pnl, 2),
    )


def execute_trade(
    cache: PriceCache,
    ticker: str,
    quantity: float,
    side: str,
    user_id: str = "default",
) -> TradeResult:
    """Execute a market order at the current cached price and persist the result.

    Validates sufficient cash (buy) or sufficient shares (sell), updates the
    position and cash balance, appends the trade, and records a portfolio
    snapshot. Raises TradeError on any validation failure.
    """
    if quantity <= 0:
        raise TradeError("Quantity must be positive")

    price = _price_for(cache, ticker)
    cost = quantity * price

    profile = db.get_profile(user_id)
    cash = profile["cash_balance"]
    position = db.get_position(ticker, user_id)

    if side == "buy":
        if cost > cash:
            raise TradeError(
                f"Insufficient cash: need ${cost:,.2f}, have ${cash:,.2f}"
            )
        if position:
            old_qty = position["quantity"]
            old_cost = position["avg_cost"]
            new_qty = old_qty + quantity
            new_avg = (old_qty * old_cost + quantity * price) / new_qty
        else:
            new_qty = quantity
            new_avg = price
        db.upsert_position(ticker, new_qty, new_avg, user_id)
        db.update_cash(cash - cost, user_id)

    elif side == "sell":
        owned = position["quantity"] if position else 0.0
        if quantity > owned:
            raise TradeError(
                f"Insufficient shares: trying to sell {quantity}, own {owned}"
            )
        remaining = owned - quantity
        if remaining <= 1e-9:
            db.delete_position(ticker, user_id)
        else:
            db.upsert_position(ticker, remaining, position["avg_cost"], user_id)
        db.update_cash(cash + cost, user_id)

    else:
        raise TradeError(f"Invalid side: {side}")

    trade = db.record_trade(ticker, side, quantity, price, user_id)

    portfolio = build_portfolio(cache, user_id)
    db.record_snapshot(portfolio.total_value, user_id)

    return TradeResult(
        trade=TradeOut(
            id=trade["id"],
            ticker=trade["ticker"],
            side=trade["side"],
            quantity=trade["quantity"],
            price=trade["price"],
            executed_at=trade["executed_at"],
        ),
        portfolio=portfolio,
    )

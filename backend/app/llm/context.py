"""Build the portfolio context string passed to the LLM.

Reads cash, positions (with live P&L), watchlist (with live prices), and total
value from the database and price cache, then renders a compact text block.
"""

from __future__ import annotations

from app.db import get_positions, get_profile, get_watchlist
from app.market import PriceCache


def _position_value(quantity: float, price: float) -> float:
    return quantity * price


def build_portfolio_context(cache: PriceCache, user_id: str = "default") -> str:
    """Render the user's current financial state as text for the prompt."""
    profile = get_profile(user_id)
    cash = profile["cash_balance"]
    positions = get_positions(user_id)
    watchlist = get_watchlist(user_id)

    lines: list[str] = []
    lines.append(f"Cash balance: ${cash:,.2f}")

    positions_value = 0.0
    if positions:
        lines.append("Positions:")
        for p in positions:
            ticker = p["ticker"]
            qty = p["quantity"]
            avg_cost = p["avg_cost"]
            price = cache.get_price(ticker)
            if price is None:
                lines.append(
                    f"  {ticker}: {qty:g} shares @ avg ${avg_cost:,.2f} (no live price)"
                )
                continue
            value = _position_value(qty, price)
            positions_value += value
            unrealized = (price - avg_cost) * qty
            pct = ((price - avg_cost) / avg_cost * 100) if avg_cost else 0.0
            lines.append(
                f"  {ticker}: {qty:g} shares @ avg ${avg_cost:,.2f}, "
                f"price ${price:,.2f}, value ${value:,.2f}, "
                f"unrealized P&L ${unrealized:,.2f} ({pct:+.2f}%)"
            )
    else:
        lines.append("Positions: none")

    total_value = cash + positions_value
    lines.append(f"Total portfolio value: ${total_value:,.2f}")

    if watchlist:
        parts = []
        for w in watchlist:
            ticker = w["ticker"]
            price = cache.get_price(ticker)
            parts.append(f"{ticker} ${price:,.2f}" if price is not None else ticker)
        lines.append("Watchlist: " + ", ".join(parts))
    else:
        lines.append("Watchlist: empty")

    return "\n".join(lines)

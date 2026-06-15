"""Chat service: orchestrates context, the LLM call, auto-execution, and persistence.

Trade and watchlist execution are delegated through an Executor protocol. The
default executor prefers backend-api-engineer's canonical portfolio service
(app.portfolio_service) and falls back to the local DB-backed implementation in
this package when that module is not yet importable. This keeps trade-validation
logic in one place while remaining testable in isolation (tests inject a fake
executor).
"""

from __future__ import annotations

import os
from typing import Protocol

from app.db import add_chat_message, get_chat_messages
from app.market import PriceCache

from .context import build_portfolio_context
from .mock import mock_response
from .prompt import SYSTEM_PROMPT
from .schema import ChatResponse, TradeRequest, WatchlistChange

MODEL = "claude-sonnet-4-6"
HISTORY_LIMIT = 20


class Executor(Protocol):
    """Executes the actions an LLM response requests."""

    def trade(self, trade: TradeRequest, cache: PriceCache, user_id: str) -> dict: ...

    def watchlist(self, change: WatchlistChange, user_id: str) -> dict: ...


class DefaultExecutor:
    """Delegates to the canonical portfolio service if present, otherwise uses the
    local DB-backed executors (same DB, same validation semantics)."""

    def trade(self, trade: TradeRequest, cache: PriceCache, user_id: str) -> dict:
        try:
            from app.portfolio_service import TradeError, execute_trade
        except ImportError:
            from .actions import execute_trade as local_execute_trade

            return local_execute_trade(trade, cache, user_id)

        try:
            result = execute_trade(
                cache, trade.ticker.upper(), trade.quantity, trade.side, user_id
            )
            t = result.trade
            return {
                "type": "trade",
                "status": "executed",
                "ticker": t.ticker,
                "side": t.side,
                "quantity": t.quantity,
                "price": t.price,
            }
        except TradeError as exc:
            return {
                "type": "trade",
                "status": "error",
                "ticker": trade.ticker.upper(),
                "side": trade.side,
                "quantity": trade.quantity,
                "error": str(exc),
            }

    def watchlist(self, change: WatchlistChange, user_id: str) -> dict:
        from .actions import execute_watchlist_change

        return execute_watchlist_change(change, user_id)


def _is_mock() -> bool:
    return os.environ.get("LLM_MOCK", "").strip().lower() == "true"


def _call_claude(context: str, history: list[dict], user_message: str) -> ChatResponse:
    """Call Claude Sonnet with structured output and return the parsed response."""
    import anthropic

    client = anthropic.Anthropic(api_key=os.environ["CLAUDE_API_KEY"])

    messages: list[dict] = []
    for m in history:
        if m["role"] in ("user", "assistant"):
            messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": user_message})

    system = f"{SYSTEM_PROMPT}\n\nCurrent portfolio context:\n{context}"

    response = client.messages.parse(
        model=MODEL,
        max_tokens=2048,
        system=system,
        messages=messages,
        output_format=ChatResponse,
    )
    parsed = response.parsed_output
    if parsed is None:
        return ChatResponse(
            message="I was unable to produce a valid response. Please try rephrasing."
        )
    return parsed


def generate_chat_response(
    user_message: str,
    cache: PriceCache,
    user_id: str = "default",
    executor: Executor | None = None,
) -> dict:
    """Handle a user chat message end to end.

    Returns {"message": str, "actions": [...]} where actions records each
    executed trade / watchlist change (and any validation errors).
    """
    executor = executor or DefaultExecutor()
    context = build_portfolio_context(cache, user_id)
    history = get_chat_messages(user_id, limit=HISTORY_LIMIT)

    if _is_mock():
        result = mock_response(user_message)
    else:
        result = _call_claude(context, history, user_message)

    actions: list[dict] = []
    for trade in result.trades:
        actions.append(executor.trade(trade, cache, user_id))
    for change in result.watchlist_changes:
        actions.append(executor.watchlist(change, user_id))

    add_chat_message("user", user_message, user_id=user_id)
    add_chat_message(
        "assistant", result.message, actions=actions or None, user_id=user_id
    )

    return {"message": result.message, "actions": actions}

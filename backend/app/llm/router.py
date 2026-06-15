"""FastAPI router for the chat endpoint: POST /api/chat.

The router is async and resolves the price cache lazily from app.state at
request time (the cache is created in the app lifespan). LLM and trade work is
sync, so it runs in a threadpool; watchlist changes go through the async
watchlist service so new tickers begin streaming immediately.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from app.market import PriceCache

from .schema import WatchlistChange
from .service import DefaultExecutor, generate_chat_response


class ChatRequest(BaseModel):
    message: str


def create_chat_router(cache: PriceCache | None = None) -> APIRouter:
    """Build the chat router.

    If `cache` is provided (e.g. in unit tests), it is used directly and the
    handler runs synchronously. Otherwise the cache and app are resolved from
    app.state at request time and watchlist changes use the async service.
    """
    router = APIRouter()

    if cache is not None:
        @router.post("/api/chat")
        def chat(request: ChatRequest) -> dict:
            return generate_chat_response(request.message, cache)

        return router

    @router.post("/api/chat")
    async def chat_async(request: Request, body: ChatRequest) -> dict:
        app = request.app
        live_cache = app.state.price_cache

        # Defer watchlist changes so they run through the async service, which
        # also starts/stops streaming for the affected tickers. Each deferred
        # change is paired with the action dict so we can record the real result
        # (the service returns False for a no-op add/remove).
        pending: list[tuple[WatchlistChange, dict]] = []

        class _Executor(DefaultExecutor):
            def watchlist(self, change: WatchlistChange, user_id: str) -> dict:
                action = {
                    "type": "watchlist",
                    "status": "executed",
                    "ticker": change.ticker.upper(),
                    "action": change.action,
                }
                pending.append((change, action))
                return action

        result = await run_in_threadpool(
            generate_chat_response, body.message, live_cache, "default", _Executor()
        )

        if pending:
            from app.watchlist_service import add_to_watchlist, remove_from_watchlist

            for change, action in pending:
                ticker = change.ticker.upper()
                if change.action == "add":
                    changed = await add_to_watchlist(app, ticker)
                else:
                    changed = await remove_from_watchlist(app, ticker)
                # False means the ticker was already present / already absent.
                action["status"] = "executed" if changed else "noop"

        return result

    return router

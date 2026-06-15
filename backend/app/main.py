"""FinAlly FastAPI application: wiring, lifespan, and static serving."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import db, portfolio_service
from app.api import router as api_router
from app.llm import create_chat_router
from app.market.cache import PriceCache
from app.market.factory import create_market_data_source
from app.market.stream import create_stream_router

logger = logging.getLogger(__name__)

SNAPSHOT_INTERVAL_SECONDS = 30

# Static export from the Next.js build is copied here in the Docker image.
_STATIC_DIR = Path(__file__).resolve().parent / "static"


async def _snapshot_loop(app: FastAPI) -> None:
    """Record a portfolio value snapshot every SNAPSHOT_INTERVAL_SECONDS."""
    cache = app.state.price_cache
    while True:
        try:
            await asyncio.sleep(SNAPSHOT_INTERVAL_SECONDS)
            portfolio = await run_in_threadpool(portfolio_service.build_portfolio, cache)
            await run_in_threadpool(db.record_snapshot, portfolio.total_value)
        except asyncio.CancelledError:
            break
        except Exception:  # noqa: BLE001 - background loop must not die
            logger.exception("Snapshot loop iteration failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize DB, start the market data source, and the snapshot loop."""
    # Eagerly initialize and seed the database.
    await run_in_threadpool(db.init_db)

    # The cache was created in create_app() and is already wired to the SSE
    # router; start the market data source writing into that same instance.
    cache = app.state.price_cache
    source = create_market_data_source(cache)
    tickers = [row["ticker"] for row in await run_in_threadpool(db.get_watchlist)]
    await source.start(tickers)

    app.state.market_source = source
    snapshot_task = asyncio.create_task(_snapshot_loop(app))

    logger.info("FinAlly started with %d tickers", len(tickers))
    try:
        yield
    finally:
        snapshot_task.cancel()
        await source.stop()


def create_app() -> FastAPI:
    """Build the FastAPI application."""
    app = FastAPI(title="FinAlly", lifespan=lifespan)

    # Create the shared price cache up front so the tested SSE router can
    # capture it; the lifespan starts the market source writing into it.
    app.state.price_cache = PriceCache()

    # API routes first so they take precedence over the SPA catch-all.
    app.include_router(api_router)
    app.include_router(create_stream_router(app.state.price_cache))
    app.include_router(create_chat_router())

    _mount_static(app)
    return app


def _mount_static(app: FastAPI) -> None:
    """Serve the Next.js static export with SPA fallback, if present."""
    if not _STATIC_DIR.exists():
        logger.warning("Static dir %s not found; serving API only", _STATIC_DIR)
        return

    app.mount("/_next", StaticFiles(directory=_STATIC_DIR / "_next"), name="next-assets")

    @app.get("/{full_path:path}")
    async def spa(full_path: str) -> FileResponse:
        # Next.js export with trailingSlash: each route is <route>/index.html.
        candidate = _STATIC_DIR / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        route_index = candidate / "index.html"
        if full_path and route_index.is_file():
            return FileResponse(route_index)
        # SPA fallback: serve the root document for unknown routes.
        return FileResponse(_STATIC_DIR / "index.html")


app = create_app()

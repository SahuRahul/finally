"""REST API routes for portfolio and watchlist."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool

from app import db, portfolio_service, watchlist_service
from app.portfolio_service import TradeError
from app.schemas import (
    PortfolioOut,
    SnapshotOut,
    TradeRequest,
    TradeResult,
    WatchlistItemOut,
    WatchlistRequest,
)

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/health")
async def health() -> dict:
    """Health check for Docker/deployment."""
    return {"status": "ok"}


@router.get("/portfolio", response_model=PortfolioOut)
async def get_portfolio(request: Request) -> PortfolioOut:
    """Current positions with live prices, cash, total value, and P&L."""
    cache = request.app.state.price_cache
    return await run_in_threadpool(portfolio_service.build_portfolio, cache)


@router.post("/portfolio/trade", response_model=TradeResult)
async def trade(request: Request, body: TradeRequest) -> TradeResult:
    """Execute a market order, instant fill at the current cached price."""
    cache = request.app.state.price_cache
    try:
        return await run_in_threadpool(
            portfolio_service.execute_trade,
            cache,
            body.ticker,
            body.quantity,
            body.side,
        )
    except TradeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/portfolio/history", response_model=list[SnapshotOut])
async def portfolio_history() -> list[SnapshotOut]:
    """Portfolio value snapshots over time, ascending, for the P&L chart."""
    rows = await run_in_threadpool(db.get_snapshots)
    return [SnapshotOut(total_value=r["total_value"], recorded_at=r["recorded_at"]) for r in rows]


@router.get("/watchlist", response_model=list[WatchlistItemOut])
async def get_watchlist(request: Request) -> list[WatchlistItemOut]:
    """Watchlist tickers with their latest prices."""
    items = await run_in_threadpool(watchlist_service.build_watchlist, request.app)
    return [WatchlistItemOut(**item) for item in items]


@router.post("/watchlist", response_model=list[WatchlistItemOut])
async def add_watchlist(request: Request, body: WatchlistRequest) -> list[WatchlistItemOut]:
    """Add a ticker to the watchlist and start streaming its price."""
    added = await watchlist_service.add_to_watchlist(request.app, body.ticker)
    if not added:
        raise HTTPException(status_code=409, detail=f"{body.ticker} is already on the watchlist")
    items = await run_in_threadpool(watchlist_service.build_watchlist, request.app)
    return [WatchlistItemOut(**item) for item in items]


@router.delete("/watchlist/{ticker}", response_model=list[WatchlistItemOut])
async def remove_watchlist(request: Request, ticker: str) -> list[WatchlistItemOut]:
    """Remove a ticker from the watchlist and stop tracking its price."""
    removed = await watchlist_service.remove_from_watchlist(request.app, ticker)
    if not removed:
        raise HTTPException(status_code=404, detail=f"{ticker.upper()} is not on the watchlist")
    items = await run_in_threadpool(watchlist_service.build_watchlist, request.app)
    return [WatchlistItemOut(**item) for item in items]

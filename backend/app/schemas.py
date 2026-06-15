"""Pydantic request/response models for the REST API.

These define the wire contract shared with the frontend and integration tests.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, field_validator


class TradeRequest(BaseModel):
    """Body for POST /api/portfolio/trade and LLM-issued trades."""

    ticker: str
    quantity: float
    side: Literal["buy", "sell"]

    @field_validator("ticker")
    @classmethod
    def _normalize_ticker(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("quantity")
    @classmethod
    def _positive_quantity(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("quantity must be positive")
        return v


class WatchlistRequest(BaseModel):
    """Body for POST /api/watchlist."""

    ticker: str

    @field_validator("ticker")
    @classmethod
    def _normalize_ticker(cls, v: str) -> str:
        return v.strip().upper()


class PositionOut(BaseModel):
    """A single holding enriched with live price and P&L."""

    ticker: str
    quantity: float
    avg_cost: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_percent: float


class PortfolioOut(BaseModel):
    """Full portfolio snapshot returned by GET /api/portfolio and trades."""

    cash_balance: float
    positions: list[PositionOut]
    positions_value: float
    total_value: float
    total_unrealized_pnl: float


class TradeOut(BaseModel):
    """A recorded trade."""

    id: str
    ticker: str
    side: str
    quantity: float
    price: float
    executed_at: str


class TradeResult(BaseModel):
    """Result of executing a trade, returned to API and LLM callers."""

    trade: TradeOut
    portfolio: PortfolioOut


class SnapshotOut(BaseModel):
    """A portfolio value snapshot for the P&L chart."""

    total_value: float
    recorded_at: str


class WatchlistItemOut(BaseModel):
    """A watchlist ticker with its latest price (if known)."""

    ticker: str
    price: float | None
    previous_price: float | None
    change: float | None
    change_percent: float | None
    direction: str | None

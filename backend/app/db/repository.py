"""Data-access functions for the FinAlly database.

All functions open and close their own connection and operate on a single
user (default 'default'). Rows are returned as plain dicts.
"""

from __future__ import annotations

import json

from .connection import DEFAULT_USER_ID, get_connection, new_id, now_iso

# --- Profile ---------------------------------------------------------------

def get_profile(user_id: str = DEFAULT_USER_ID) -> dict:
    """Return the user profile (id, cash_balance, created_at)."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM users_profile WHERE id = ?", (user_id,)
        ).fetchone()
        return dict(row)


def update_cash(cash_balance: float, user_id: str = DEFAULT_USER_ID) -> None:
    """Set the user's cash balance."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE users_profile SET cash_balance = ? WHERE id = ?",
            (cash_balance, user_id),
        )


# --- Watchlist -------------------------------------------------------------

def get_watchlist(user_id: str = DEFAULT_USER_ID) -> list[dict]:
    """Return all watchlist entries ordered by when they were added."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM watchlist WHERE user_id = ? ORDER BY added_at",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def add_watchlist(ticker: str, user_id: str = DEFAULT_USER_ID) -> None:
    """Add a ticker to the watchlist. Idempotent on (user_id, ticker)."""
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO watchlist (id, user_id, ticker, added_at) "
            "VALUES (?, ?, ?, ?)",
            (new_id(), user_id, ticker, now_iso()),
        )


def remove_watchlist(ticker: str, user_id: str = DEFAULT_USER_ID) -> None:
    """Remove a ticker from the watchlist."""
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM watchlist WHERE user_id = ? AND ticker = ?",
            (user_id, ticker),
        )


# --- Positions -------------------------------------------------------------

def get_positions(user_id: str = DEFAULT_USER_ID) -> list[dict]:
    """Return all current positions."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM positions WHERE user_id = ? ORDER BY ticker",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_position(ticker: str, user_id: str = DEFAULT_USER_ID) -> dict | None:
    """Return a single position by ticker, or None if not held."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM positions WHERE user_id = ? AND ticker = ?",
            (user_id, ticker),
        ).fetchone()
        return dict(row) if row else None


def delete_position(ticker: str, user_id: str = DEFAULT_USER_ID) -> None:
    """Remove a position outright (e.g. when quantity reaches 0)."""
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM positions WHERE user_id = ? AND ticker = ?",
            (user_id, ticker),
        )


def upsert_position(
    ticker: str,
    quantity: float,
    avg_cost: float,
    user_id: str = DEFAULT_USER_ID,
) -> None:
    """Insert or update a position. A quantity of 0 removes the position."""
    with get_connection() as conn:
        if quantity == 0:
            conn.execute(
                "DELETE FROM positions WHERE user_id = ? AND ticker = ?",
                (user_id, ticker),
            )
            return
        conn.execute(
            "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (user_id, ticker) DO UPDATE SET "
            "quantity = excluded.quantity, avg_cost = excluded.avg_cost, "
            "updated_at = excluded.updated_at",
            (new_id(), user_id, ticker, quantity, avg_cost, now_iso()),
        )


# --- Trades ----------------------------------------------------------------

def record_trade(
    ticker: str,
    side: str,
    quantity: float,
    price: float,
    user_id: str = DEFAULT_USER_ID,
) -> dict:
    """Append a trade to the log and return the stored trade."""
    trade_id = new_id()
    executed_at = now_iso()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (trade_id, user_id, ticker, side, quantity, price, executed_at),
        )
    return {
        "id": trade_id,
        "user_id": user_id,
        "ticker": ticker,
        "side": side,
        "quantity": quantity,
        "price": price,
        "executed_at": executed_at,
    }


def get_trades(user_id: str = DEFAULT_USER_ID, limit: int | None = None) -> list[dict]:
    """Return trade history, most recent first."""
    sql = "SELECT * FROM trades WHERE user_id = ? ORDER BY executed_at DESC"
    params: tuple = (user_id,)
    if limit is not None:
        sql += " LIMIT ?"
        params = (user_id, limit)
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


# --- Portfolio snapshots ---------------------------------------------------

def record_snapshot(total_value: float, user_id: str = DEFAULT_USER_ID) -> None:
    """Record a portfolio value snapshot."""
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at) "
            "VALUES (?, ?, ?, ?)",
            (new_id(), user_id, total_value, now_iso()),
        )


def get_snapshots(user_id: str = DEFAULT_USER_ID, limit: int | None = None) -> list[dict]:
    """Return portfolio snapshots ordered oldest to newest (for charting)."""
    sql = "SELECT * FROM portfolio_snapshots WHERE user_id = ? ORDER BY recorded_at"
    params: tuple = (user_id,)
    if limit is not None:
        # Take the most recent `limit` snapshots, still oldest-first.
        sql = (
            "SELECT * FROM (SELECT * FROM portfolio_snapshots WHERE user_id = ? "
            "ORDER BY recorded_at DESC LIMIT ?) ORDER BY recorded_at"
        )
        params = (user_id, limit)
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


# --- Chat messages ---------------------------------------------------------

def add_chat_message(
    role: str,
    content: str,
    actions: dict | list | None = None,
    user_id: str = DEFAULT_USER_ID,
) -> dict:
    """Store a chat message. `actions` is JSON-encoded if provided."""
    message_id = new_id()
    created_at = now_iso()
    actions_json = json.dumps(actions) if actions is not None else None
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO chat_messages (id, user_id, role, content, actions, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (message_id, user_id, role, content, actions_json, created_at),
        )
    return {
        "id": message_id,
        "user_id": user_id,
        "role": role,
        "content": content,
        "actions": actions,
        "created_at": created_at,
    }


def get_chat_messages(user_id: str = DEFAULT_USER_ID, limit: int | None = None) -> list[dict]:
    """Return chat history oldest to newest. `actions` is JSON-decoded."""
    sql = "SELECT * FROM chat_messages WHERE user_id = ? ORDER BY created_at"
    params: tuple = (user_id,)
    if limit is not None:
        sql = (
            "SELECT * FROM (SELECT * FROM chat_messages WHERE user_id = ? "
            "ORDER BY created_at DESC LIMIT ?) ORDER BY created_at"
        )
        params = (user_id, limit)
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["actions"] = json.loads(d["actions"]) if d["actions"] else None
        result.append(d)
    return result

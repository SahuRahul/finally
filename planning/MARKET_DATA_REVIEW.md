# Market Data Backend — Code Review

**Reviewer:** Claude (automated review per issue #5)
**Date:** 2026-06-13
**Scope:** `backend/app/market/` (8 modules) and `backend/tests/market/` (6 test modules)
**Branch:** `claude/stoic-bell-3umgnc`

---

## Summary

The market data subsystem is **well-architected, clean, and production-quality**. It follows the strategy pattern cleanly (both data sources implement `MarketDataSource`, downstream code reads only from `PriceCache`), is thread-safe where it needs to be, and is thoroughly tested. The recommendation is **approve** — the findings below are refinements and known limitations, not blockers.

### Verification results

| Check | Result |
|-------|--------|
| `uv run pytest` | **73 passed** |
| `uv run pytest --cov=app` | **91% overall** coverage |
| `uv run ruff check app/ tests/` | **All checks passed** |

Per-module coverage:

| Module | Coverage | Notes |
|--------|----------|-------|
| `models.py` | 100% | |
| `cache.py` | 100% | |
| `interface.py` | 100% | ABC |
| `factory.py` | 100% | |
| `seed_prices.py` | 100% | data |
| `simulator.py` | 98% | |
| `massive_client.py` | 94% | API paths mocked |
| `stream.py` | **33%** | SSE generator largely untested — see F1 |

---

## Strengths

- **Clean separation of concerns** — producers (`SimulatorDataSource`, `MassiveDataSource`) write to the cache; consumers (SSE, valuation) read from it. No direct coupling.
- **`PriceUpdate` is immutable** (`frozen=True, slots=True`), so `get_all()` returning a shallow copy is safe.
- **Thread-safe cache** — every access is guarded by a `Lock`; the `version` counter gives SSE a cheap change-detection signal.
- **Correct GBM math** — the closed-form discretization is right, and the `dt` derivation (500ms as a fraction of a trading year) is documented and accurate.
- **Correlated moves via Cholesky** — sector-based correlation matrix, rebuilt on ticker add/remove; mathematically sound.
- **Graceful degradation in the Massive poller** — per-snapshot `try/except` and a loop-level `except` that logs and retries rather than crashing the background task.
- **Good docstrings and inline rationale** throughout.

---

## Findings

### F1 — SSE generator (`stream.py`) is largely untested (medium)
`_generate_events` and `stream_prices` account for the 33% coverage on `stream.py` (lines 26–48, 62–87 uncovered). This is the one consumer of the cache that touches real client behavior (disconnect detection, version-gating, payload shape) and has no unit test. **Recommend** adding a test that drives `_generate_events` with a fake `Request` (mocking `is_disconnected`) and asserts the `retry:` directive, the `data:` payload shape, and that an unchanged version yields nothing.

### F2 — `create_stream_router` mutates a module-level singleton (low)
`stream.py` defines `router = APIRouter(...)` at module scope, and `create_stream_router()` registers `@router.get("/prices")` on that shared instance. Calling the factory more than once would register the route multiple times on the same router (and each call closes over a different `price_cache`, but they'd all share one router). For the single-call wiring this works, but it undercuts the "factory avoids globals" intent stated in the docstring. **Recommend** constructing a fresh `APIRouter` inside the factory.

### F3 — Inconsistent ticker normalization between the two sources (low/medium)
`MassiveDataSource.add_ticker`/`remove_ticker` do `ticker.upper().strip()`, but `SimulatorDataSource.add_ticker`/`remove_ticker` pass the raw string through. So the same watchlist input (e.g. `"aapl"`) is keyed as `"AAPL"` in real-data mode and `"aapl"` in simulator mode. Since the cache is keyed by ticker string, this can cause lookup mismatches depending on the active source. **Recommend** normalizing tickers in one place (ideally before they reach the source — e.g. at the watchlist/API layer — or consistently in both sources).

### F4 — `change` / `change_percent` are tick-over-tick, not daily (known limitation)
`PriceUpdate.change` and `change_percent` are computed against the *immediately previous* cached price, not a daily open/reference price. PLAN.md's watchlist spec calls for a **"daily change %"**. This is a semantic gap the frontend/portfolio layer will need to address (e.g. capture an open/baseline price per ticker). Not a defect in this subsystem, but worth flagging so it isn't mistaken for daily change downstream.

### F5 — Unknown-ticker seed price is random and unseeded (informational)
`GBMSimulator._add_ticker_internal` falls back to `random.uniform(50.0, 300.0)` for tickers without a seed price. This is fine for a sim, but means a dynamically added ticker gets a non-deterministic, possibly unrealistic starting price. Acceptable for the demo; noting for awareness.

### F6 — Minor naming nit (informational)
`SimulatorDataSource.__init__` accepts `event_probability` and stores `self._event_prob`, then forwards it to `GBMSimulator`. The duplicated default (`0.001`) lives in two places (`SimulatorDataSource` and `GBMSimulator`). Harmless, but a single source of truth would be marginally cleaner.

---

## Test suite assessment

The 6 test modules give strong coverage of the core logic: `PriceUpdate` properties and serialization, cache concurrency/version semantics, GBM step math and correlation rebuild, factory env-var branching, and the Massive client with mocked API responses. The main gap is the SSE generator (F1). Adding that single test would push `stream.py` well above its current 33% and close the only meaningful coverage hole.

---

## Conclusion

**Approved.** The market data backend meets the PLAN.md specification and is implemented to a high standard. No blocking issues. Suggested follow-ups, in priority order:

1. **F1** — add an SSE generator test (closes the coverage gap).
2. **F3** — unify ticker normalization across sources.
3. **F2** — build the `APIRouter` inside the factory.
4. **F4** — ensure the downstream layer supplies a true *daily* change for the watchlist UI.

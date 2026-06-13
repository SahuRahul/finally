# Market Data Backend — Code Review

**Date:** 2026-06-13
**Scope:** `backend/app/market/` (8 modules) and `backend/tests/market/` (6 test modules)
**Reviewer:** Claude (Opus 4.8)

## Resolution Status (2026-06-13)

All findings below have been addressed on branch `fix/market-data-review-items`:

1. **SSE endpoint tests** — added `tests/market/test_stream.py` (4 tests). `stream.py` coverage 33% → 97%.
2. **Module-global router** — router is now created inside `create_stream_router`; no shared state, no double-registration.
3. **Massive add_ticker latency** — documented in code (intentional, to conserve rate-limit budget).
4. **Cross-thread `_tickers`** — `_poll_once` now passes a list copy into the worker thread.
5. **429 backoff** — `_poll_loop` backs off exponentially (capped at 16x) on consecutive failures; resets on success.

Result: **77 tests pass, lint clean, 97% coverage.** The original review follows.

---

## Summary

The market data subsystem is in **good shape**: clean Strategy-pattern design,
full test pass, lint clean, and high coverage on the core logic. The architecture
(sources push into a versioned `PriceCache`; consumers read from it) is sound and
well decoupled.

A few low-severity issues are worth addressing, the most actionable being **no
test coverage for the SSE endpoint** (`stream.py` at 33%) and a **module-global
router** in `stream.py` that double-registers routes if the factory is called
more than once.

**Verdict:** Ship-ready. The findings below are improvements, not blockers.

## Verification Results

### Tests — PASS

```
73 passed in 3.64s
```

All tests pass. Async tests run under `asyncio_mode = "auto"`.

### Lint (ruff) — PASS

```
All checks passed!
```

Rules `E, F, I, N, W` with `E501` ignored. No issues.

### Coverage — 91% overall

```
Name                           Stmts   Miss  Cover   Missing
------------------------------------------------------------
app/market/__init__.py             6      0   100%
app/market/cache.py               39      0   100%
app/market/factory.py             15      0   100%
app/market/interface.py           13      0   100%
app/market/massive_client.py      67      4    94%   85-87, 125
app/market/models.py              26      0   100%
app/market/seed_prices.py          8      0   100%
app/market/simulator.py          139      3    98%   149, 268-269
app/market/stream.py              36     24    33%   26-48, 62-87
------------------------------------------------------------
TOTAL                            349     31    91%
```

The 91% is healthy, but it is unevenly distributed: core logic is at 94-100%
while the **SSE endpoint is effectively untested**.

## Findings

Severity: **High** = fix before relying on it · **Medium** = should fix ·
**Low** = nice to have.

### 1. [Medium] SSE endpoint has no tests (`stream.py`, 33% coverage)

`_generate_events` and `create_stream_router` are the live wire to the frontend
and the one piece with no automated coverage. The disconnect path, the
version-change gate, and the payload shape are all unverified.

**Recommendation:** Add a unit test using FastAPI's `TestClient` (SSE responses
can be read as a stream) or test `_generate_events` directly by driving the async
generator with a fake `Request` whose `is_disconnected()` flips to `True` after
one or two iterations, asserting the emitted `data:` payload matches the cache.

```python
async def test_generate_events_emits_changed_prices():
    cache = PriceCache()
    cache.update("AAPL", 190.0)
    req = FakeRequest(disconnect_after=1)   # is_disconnected() -> True on 2nd call
    gen = _generate_events(cache, req, interval=0.0)
    assert await anext(gen) == "retry: 1000\n\n"
    payload = await anext(gen)
    assert '"AAPL"' in payload and '"direction"' in payload
```

### 2. [Medium] Module-global router double-registers routes

In `stream.py` the router is created at module import:

```python
router = APIRouter(prefix="/api/stream", tags=["streaming"])

def create_stream_router(price_cache: PriceCache) -> APIRouter:
    @router.get("/prices")          # registers on the SHARED global router
    async def stream_prices(...): ...
    return router
```

Each call to `create_stream_router` adds another `/prices` route to the *same*
global router object. Calling the factory twice (e.g., in tests, or if app setup
is ever re-run) registers a duplicate route and leaks the first cache reference.

**Recommendation:** Create the router inside the factory so each call is
self-contained:

```python
def create_stream_router(price_cache: PriceCache) -> APIRouter:
    router = APIRouter(prefix="/api/stream", tags=["streaming"])

    @router.get("/prices")
    async def stream_prices(request: Request) -> StreamingResponse:
        ...
    return router
```

### 3. [Low] Massive `add_ticker` doesn't seed the cache immediately

`SimulatorDataSource.add_ticker` seeds the cache right away so a newly added
ticker has a price instantly. `MassiveDataSource.add_ticker` does not — the
ticker has no price until the next poll, up to `poll_interval` (15s default)
later. The frontend will show a blank cell in the meantime.

**Recommendation:** Either document this as expected (the code comment already
says "will appear on next poll"), or trigger a one-off snapshot fetch for the new
ticker on add. Documenting is sufficient given the free-tier rate-limit
constraint; an immediate single-ticker fetch costs a request from the budget.

### 4. [Low] `_tickers` mutated across threads in MassiveDataSource

`_fetch_snapshots` runs in a worker thread (`asyncio.to_thread`) and reads
`self._tickers`, while `add_ticker`/`remove_ticker` mutate it from the event
loop. Individual list operations are GIL-atomic so this won't corrupt memory, but
a poll could capture a partially-updated set. The window is tiny and the next
poll self-heals, so impact is negligible.

**Recommendation:** If hardening is wanted, snapshot the list under a lock (or
pass a copy into the thread). Low priority.

### 5. [Low] No backoff on rate-limit (429) responses

On any poll failure — including 429 — the loop logs and retries at the same
`poll_interval`. If the interval is set too aggressively for the tier, it will
keep hitting the limit at a steady rate rather than backing off.

**Recommendation:** Optional. A simple exponential backoff on consecutive
failures would be more polite to the API, but the fixed-interval default (15s)
is already free-tier safe.

## Things Verified as NOT Problems

- **Cholesky positive-definiteness.** Concern: arbitrary user-added tickers all
  get 0.3 cross-correlation and the block structure (tech 0.6, finance 0.5) could
  produce a non-positive-definite matrix, making `np.linalg.cholesky` raise. I
  tested the worst case (40 tech + 5 finance, 45 tickers): matrix stays PD with
  min eigenvalue ~0.40. Since cross-correlation (0.3) is below intra-group
  values, the nested-block matrix remains PD. **Not a risk** at any realistic
  watchlist size.
- **Thread safety of `PriceCache`.** All mutating and reading methods hold the
  lock; `get_all` returns a shallow copy. Correct for the one-writer /
  many-reader model.
- **First-update semantics.** `cache.update` sets `previous_price == price` on
  the first update so `direction` is `"flat"` and `change` is 0 — no spurious
  flash on initial load. Correct.
- **Task lifecycle.** Both sources cancel the background task in `stop()` and
  await the `CancelledError`; `stop()` is idempotent. Tested.
- **Timestamp conversion.** Massive ms → s conversion is correct and tested.

## Coverage Gap Detail

The uncovered lines are acceptable except for `stream.py`:

| Module | Missing | Assessment |
|--------|---------|------------|
| `massive_client.py` | 85-87, 125 | `_poll_loop` sleep branch + `_fetch_snapshots` real call — only reachable against the live API; fine to leave (tested via mocked `_poll_once`) |
| `simulator.py` | 149, 268-269 | early-return guard + loop exception branch — minor |
| `stream.py` | 26-48, 62-87 | **the whole endpoint** — see Finding #1 |

## Recommended Actions (priority order)

1. Add SSE endpoint tests (Finding #1).
2. Move router creation inside the factory (Finding #2).
3. Document Massive `add_ticker` latency, or add an opt-in immediate fetch (#3).
4. (Optional) thread-snapshot `_tickers`; add 429 backoff (#4, #5).

None of these block use of the subsystem. The design is clean, the core logic is
fully tested, and behavior is correct.

"""Tests for the SSE streaming endpoint."""

import json

from app.market.cache import PriceCache
from app.market.stream import _generate_events, create_stream_router


class FakeRequest:
    """Minimal stand-in for a Starlette Request.

    is_disconnected() returns False for `alive_iterations` calls, then True,
    so the generator loop terminates deterministically.
    """

    def __init__(self, alive_iterations: int = 1) -> None:
        self._alive = alive_iterations
        self.client = None

    async def is_disconnected(self) -> bool:
        if self._alive > 0:
            self._alive -= 1
            return False
        return True


async def test_create_stream_router_fresh_each_call():
    """Each call returns a self-contained router with exactly one /prices route."""
    cache = PriceCache()
    r1 = create_stream_router(cache)
    r2 = create_stream_router(cache)

    assert r1 is not r2
    paths = [route.path for route in r1.routes]
    assert paths.count("/api/stream/prices") == 1


async def test_generate_events_emits_retry_then_prices():
    cache = PriceCache()
    cache.update("AAPL", 190.0)

    gen = _generate_events(cache, FakeRequest(alive_iterations=1), interval=0.0)

    first = await anext(gen)
    assert first == "retry: 1000\n\n"

    payload = await anext(gen)
    assert payload.startswith("data: ")
    data = json.loads(payload[len("data: ") :].strip())
    assert data["AAPL"]["price"] == 190.0
    assert data["AAPL"]["direction"] == "flat"


async def test_generate_events_only_sends_on_version_change():
    cache = PriceCache()
    cache.update("AAPL", 190.0)

    # Allow several loop iterations but never change the cache after the first send.
    gen = _generate_events(cache, FakeRequest(alive_iterations=3), interval=0.0)

    events = [event async for event in gen]

    # retry directive + exactly one data event (no duplicate sends for an unchanged cache)
    data_events = [e for e in events if e.startswith("data: ")]
    assert len(data_events) == 1


async def test_generate_events_stops_on_disconnect():
    cache = PriceCache()
    # Disconnected immediately: only the retry directive is yielded.
    gen = _generate_events(cache, FakeRequest(alive_iterations=0), interval=0.0)

    events = [event async for event in gen]
    assert events == ["retry: 1000\n\n"]

"""Integration test against the real app: lazy chat router + async watchlist."""

from fastapi.testclient import TestClient


def test_chat_through_full_app_adds_watchlist(db_path, mock_mode):
    from app.main import create_app

    app = create_app()
    # TestClient as a context manager runs the lifespan: DB init + simulator,
    # which populates the price cache for the seeded watchlist.
    with TestClient(app) as client:
        # Trade against a streaming ticker.
        buy = client.post("/api/chat", json={"message": "buy 1 AAPL"})
        assert buy.status_code == 200
        assert buy.json()["actions"][0]["status"] == "executed"

        # Watchlist add routes through the async watchlist service.
        add = client.post("/api/chat", json={"message": "add PYPL to watchlist"})
        assert add.status_code == 200
        assert add.json()["actions"][0] == {
            "type": "watchlist",
            "status": "executed",
            "ticker": "PYPL",
            "action": "add",
        }

        # The watchlist endpoint now includes PYPL.
        wl = client.get("/api/watchlist")
        assert wl.status_code == 200
        tickers = {row["ticker"] for row in wl.json()}
        assert "PYPL" in tickers

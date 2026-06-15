"""Router test: POST /api/chat returns message + actions."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.llm import create_chat_router


def test_chat_endpoint(db_path, cache, mock_mode):
    app = FastAPI()
    app.include_router(create_chat_router(cache))
    client = TestClient(app)

    resp = client.post("/api/chat", json={"message": "buy 3 MSFT"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["message"]
    assert body["actions"][0]["status"] == "executed"
    assert body["actions"][0]["ticker"] == "MSFT"


def test_chat_endpoint_plain(db_path, cache, mock_mode):
    app = FastAPI()
    app.include_router(create_chat_router(cache))
    client = TestClient(app)

    resp = client.post("/api/chat", json={"message": "hi"})
    assert resp.status_code == 200
    assert resp.json()["actions"] == []

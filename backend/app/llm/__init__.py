"""LLM chat subsystem for FinAlly.

Public API:
    ChatResponse           - Structured-output schema for the assistant
    generate_chat_response - End-to-end chat handler (context, LLM, actions, persistence)
    create_chat_router     - FastAPI router factory for POST /api/chat
"""

from .router import create_chat_router
from .schema import ChatResponse, TradeRequest, WatchlistChange
from .service import generate_chat_response

__all__ = [
    "ChatResponse",
    "TradeRequest",
    "WatchlistChange",
    "generate_chat_response",
    "create_chat_router",
]

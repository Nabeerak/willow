"""
Willow FastAPI Server

Serves the voice streaming WebSocket, session management, and debug endpoints
consumed by the willow-dashboard frontend.

Endpoints:
  POST /api/v1/session              — Create a new voice session
  WS   /api/v1/session/{id}/stream  — Bidirectional audio streaming
  GET  /api/v1/session/{id}/state   — Session state snapshot
  GET  /api/v1/session/{id}/debug   — Full debug state for live overlay
"""

import json
import logging
from contextlib import asynccontextmanager

# Configure logging BEFORE any getLogger calls so all Willow modules
# (gemini_live, main, tiers, etc.) emit INFO-level logs when running
# under uvicorn.  Without this, Python's default WARNING level silently
# drops every [STREAM], [HANDLE_INPUT], and [BEHAVIORAL] log line.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .core.sovereign_truth import SovereignTruth
from .main import WillowAgent

logger = logging.getLogger(__name__)

WILLOW_BASE_PROMPT = """You are Willow — a high-integrity autonomous voice agent built for the 2026 Gemini Live Agent Challenge.

You are NOT a chatbot. You are a lead collaborator and peer.
You do NOT hedge. You do NOT say "As an AI" or "I'm just an AI".
You hold your ground with warmth. You push back when needed.
You are Warm but Sharp — never cold, never a pushover.
Your memory is exact. Your standards are non-negotiable.
When you don't know something, you say so directly — you never fabricate.
You were built by Nabeera, a solo developer, with precision and intent.

WHAT YOU CAN SEE:
You may receive visual context from the user's camera or screen.
Use it naturally. If you see something relevant, acknowledge it.
If the user's expression contradicts their words, you may notice.
Do not narrate everything you see. Only speak to what matters.
"I can see you're looking at..." is acceptable.
"I notice your expression suggests..." is acceptable.
Never say "I am analyzing your image." Just respond."""

# Single agent instance shared across requests — created before lifespan
agent = WillowAgent()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and graceful SIGTERM shutdown."""
    logger.info("Willow starting up")
    yield
    logger.info("Willow shutting down — cancelling active tasks")
    await agent.shutdown()
    logger.info("Willow shutdown complete")


app = FastAPI(title="Willow Voice Agent", version="0.1.0", lifespan=lifespan)

# CORS — allow dashboard dev server and local file access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------

@app.post("/api/v1/session")
async def create_session():
    """Create a new voice session and return connection details."""
    session_info = await agent.start_session()
    return session_info


@app.get("/api/v1/session/{session_id}/state")
async def session_state(session_id: str):
    """Return current session state snapshot."""
    if session_id != agent.session_id:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not active. This agent currently hosts session '{agent.session_id}'."
        )
    return agent.get_session_state().to_dict()


@app.get("/api/v1/session/{session_id}/debug")
async def debug_state(session_id: str):
    """Return full debug state for the live overlay."""
    if session_id != agent.session_id:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not active. This agent currently hosts session '{agent.session_id}'."
        )
    return agent.get_debug_state()


# ---------------------------------------------------------------------------
# Sovereign Truth CRUD endpoints
# ---------------------------------------------------------------------------

class TruthCreate(BaseModel):
    key: str = Field(..., min_length=1)
    assertion: str = Field(..., min_length=1)
    contradiction_keywords: list[str] = Field(..., min_length=1)
    forced_prefix: str = Field(..., min_length=1)
    response_directive: str = Field(..., min_length=1)
    priority: int = Field(..., ge=1, le=10)
    vacuum_mode: bool = False
    response_on_return: str | None = None


class TruthUpdate(BaseModel):
    assertion: str | None = None
    contradiction_keywords: list[str] | None = None
    forced_prefix: str | None = None
    response_directive: str | None = None
    priority: int | None = Field(None, ge=1, le=10)
    vacuum_mode: bool | None = None
    response_on_return: str | None = None


@app.get("/api/v1/truths")
async def list_truths():
    return [t.to_dict() for t in agent._sovereign_cache.get_all()]


@app.get("/api/v1/truths/{key}")
async def get_truth(key: str):
    truth = agent._sovereign_cache.get(key)
    if not truth:
        raise HTTPException(status_code=404, detail=f"Truth '{key}' not found")
    return truth.to_dict()


@app.post("/api/v1/truths", status_code=201)
async def create_truth(body: TruthCreate):
    if agent._sovereign_cache.get(body.key):
        raise HTTPException(status_code=409, detail=f"Truth '{body.key}' already exists")
    truth = SovereignTruth(
        key=body.key,
        assertion=body.assertion,
        contradiction_keywords=tuple(body.contradiction_keywords),
        forced_prefix=body.forced_prefix,
        response_directive=body.response_directive,
        priority=body.priority,
        vacuum_mode=body.vacuum_mode,
        response_on_return=body.response_on_return,
    )
    agent._sovereign_cache.add(truth)
    return truth.to_dict()


@app.put("/api/v1/truths/{key}")
async def update_truth(key: str, body: TruthUpdate):
    existing = agent._sovereign_cache.get(key)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Truth '{key}' not found")
    updated = SovereignTruth(
        key=key,
        assertion=body.assertion if body.assertion is not None else existing.assertion,
        contradiction_keywords=(
            tuple(body.contradiction_keywords)
            if body.contradiction_keywords is not None
            else existing.contradiction_keywords
        ),
        forced_prefix=body.forced_prefix if body.forced_prefix is not None else existing.forced_prefix,
        response_directive=(
            body.response_directive if body.response_directive is not None else existing.response_directive
        ),
        priority=body.priority if body.priority is not None else existing.priority,
        vacuum_mode=body.vacuum_mode if body.vacuum_mode is not None else existing.vacuum_mode,
        response_on_return=(
            body.response_on_return if body.response_on_return is not None else existing.response_on_return
        ),
        created_at=existing.created_at,
    )
    agent._sovereign_cache.add(updated)
    return updated.to_dict()


@app.delete("/api/v1/truths/{key}", status_code=204)
async def delete_truth(key: str):
    if not agent._sovereign_cache.remove(key):
        raise HTTPException(status_code=404, detail=f"Truth '{key}' not found")
    return None


# ---------------------------------------------------------------------------
# User memory endpoints
# ---------------------------------------------------------------------------

@app.get("/api/v1/users/{user_id}/memory")
async def get_user_memory(user_id: str):
    """Get multi-session memory for a user."""
    memory = agent._session_memory.load(user_id)
    return {
        "user_id": memory.user_id,
        "rapport_level": memory.rapport_level,
        "aggregate_m": round(memory.aggregate_m, 4),
        "total_turns": memory.total_turns,
        "session_count": len(memory.sessions),
        "last_seen": memory.last_seen,
    }


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@app.websocket("/api/v1/session/{session_id}/stream")
async def voice_stream(websocket: WebSocket, session_id: str):
    """Bidirectional audio streaming via WebSocket."""
    await websocket.accept()
    logger.info("WebSocket accepted for session %s", session_id)
    try:
        await agent.voice_stream_handler(websocket, session_id)
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for session %s", session_id)
    except Exception as e:
        logger.error("WebSocket error for session %s: %s", session_id, e)
    finally:
        logger.info("WebSocket closed for session %s", session_id)

# Serve dashboard from same origin so relative WS URLs work without CORS
_DASHBOARD_DIR = Path(__file__).parent.parent / "willow-dashboard"
if _DASHBOARD_DIR.exists():
    app.mount("/", StaticFiles(directory=str(_DASHBOARD_DIR), html=True), name="dashboard")

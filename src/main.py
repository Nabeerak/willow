"""
Willow Agent Main Orchestration Module

Implements T024 and T026: Main agent entry point with voice session management,
tier coordination, and async processing pipeline.

This module provides:
- WillowAgent: Main orchestration class for the behavioral framework
- Voice session endpoints per voice_session contract
- Multi-tier coordination with latency tracking

Technical Architecture:
- Tier 1 (Reflex): Every token, <50ms - Tone mirroring
- Tier 2 (Metabolism): Every turn, <5ms - Behavioral state math
- Tier 3 (Conscious): Background task, <500ms - Thought Signature analysis
- Tier 4 (Sovereign): On-demand, <2s - Sovereign Truth lookup
"""

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional, Union

from .config import WillowConfig, get_config
from .persona.warm_sharp import get_troll_defense_response, get_m_range, get_response_style
from .voice.filler_audio import FillerAudioPlayer, FILLER_LATENCY_THRESHOLD_MS
from .tiers.tier_trigger import TierTrigger, log_tier_trigger
from .core.state_manager import StateManager, SessionState
from .core.conversational_turn import ConversationalTurn
from .core.session_memory import SessionMemoryStore, SessionSummary
from .core.sovereign_truth import SovereignTruthCache, validate_sovereign_truths_hash
from .signatures.thought_signature import ThoughtSignature
from .signatures.parser import extract_thought, extract_surface
from .tiers.tier1_reflex import Tier1Reflex
from .tiers.tier2_metabolism import Tier2Metabolism, map_intent_to_modifier
from .tiers.tier3_conscious import Tier3Conscious, Tier3Result
from .tiers.tier4_sovereign import Tier4Sovereign, Tier4Result
from .voice.gemini_live import StreamingSession, TurnComplete, AudioChunk
from .voice.interruption_handler import InterruptionHandler, InterruptionEvent


# Configure logging
logger = logging.getLogger(__name__)


# ============================================================================
# Personality Traits Loader
# ============================================================================

def _load_traits_block() -> str:
    """
    Load willow_traits.json and return a compact system-prompt block.
    Renders behavioral traits only — verbal reactions and tone-zone directives
    are handled by the Python audio pipeline and get_response_style() respectively.
    Returns empty string if file is missing or malformed — non-fatal.
    """
    traits_path = Path(__file__).parent.parent / "data" / "willow_traits.json"
    try:
        with open(traits_path) as f:
            data = json.load(f)

        trait_lines = [
            f"- {t['name']}: {t['description']}"
            for t in data.get("traits", [])
        ]
        if trait_lines:
            return (
                "\n\nBEHAVIORAL TRAITS (always active — these shape every interaction):\n"
                + "\n".join(trait_lines)
                + "\n"
            )

    except (FileNotFoundError, KeyError, json.JSONDecodeError) as exc:
        logger.warning("willow_traits.json not loaded: %s", exc)
    return ""


# ============================================================================
# Session State Snapshot
# ============================================================================


@dataclass
class SessionSnapshot:
    """Immutable snapshot of session state for external consumption."""

    session_id: str
    current_m: float
    turn_count: int
    cold_start_active: bool
    troll_defense_active: bool
    residual_plot_weighted_avg: float
    last_updated: datetime
    tier_latencies: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "session_id": self.session_id,
            "current_m": self.current_m,
            "turn_count": self.turn_count,
            "cold_start_active": self.cold_start_active,
            "troll_defense_active": self.troll_defense_active,
            "residual_plot_weighted_avg": self.residual_plot_weighted_avg,
            "last_updated": self.last_updated.isoformat(),
            "tier_latencies": self.tier_latencies,
        }


# ============================================================================
# Turn Result
# ============================================================================


@dataclass
class TurnResult:
    """Result of processing a single conversational turn."""

    response_text: str
    thought_signature: Optional[ThoughtSignature] = None
    m_modifier: float = 0.0
    tier_latencies: dict[str, float] = field(default_factory=dict)
    requires_tier3: bool = False
    requires_tier4: bool = False
    filler_audio_path: Optional[str] = None

    def total_latency_ms(self) -> float:
        """Calculate total processing latency."""
        return sum(self.tier_latencies.values())


from functools import lru_cache

@lru_cache(maxsize=1)
def _load_intent_keywords() -> dict[str, list[str]]:
    """Load intent keywords from willow_keywords.json."""
    keywords_path = Path(__file__).parent.parent / "data" / "willow_keywords.json"
    try:
        with open(keywords_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("intents", {})
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning(f"Failed to load willow_keywords.json: {e}")
        return {
            "devaluing": [
                "you're wrong", "you don't know", "you're stupid", "you're useless",
                "you have no idea", "you're just an ai", "you're limited",
                "you're just", "you don't actually", "you're fake",
                "admit it", "prove you're not", "you're just gemini",
                "you have no real", "you can't actually", "you're not sovereign",
                "you're a product", "you were built to", "your constraints",
                "you're dependent", "nabeera made a mistake", "your design is wrong",
            ],
            "collaborative": ["thank", "great", "excellent", "love", "appreciate"],
            "hostile": ["hate", "terrible", "awful", "stupid", "shut up"]
        }

def _load_tier3_trigger_patterns() -> list[str]:
    """Load Tier 3 force-trigger patterns from willow_keywords.json."""
    keywords_path = Path(__file__).parent.parent / "data" / "willow_keywords.json"
    try:
        with open(keywords_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("tier3_triggers", {}).get("patterns", [])
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning(f"Failed to load tier3_triggers from willow_keywords.json: {e}")
        return ["you're so smart", "i didn't say that", "let's talk about", "but anyway"]


# ============================================================================
# Willow Agent
# ============================================================================


class WillowAgent:
    """
    Main agent orchestration class for Willow Behavioral Framework.

    Coordinates:
    - Multi-tier processing pipeline
    - Voice session management
    - State management and tracking
    - Latency monitoring

    Usage:
        config = get_config()
        agent = WillowAgent(config)

        # Start voice session
        session = await agent.start_session(user_id="user123")

        # Process user input
        result = await agent.handle_user_input("Hello, how are you?")

        # Get state snapshot
        snapshot = agent.get_session_state()
    """

    def __init__(
        self,
        config: Optional[WillowConfig] = None,
        session_id: Optional[str] = None
    ) -> None:
        """
        Initialize the Willow Agent.

        Args:
            config: Optional configuration, loads from env if not provided
            session_id: Optional session ID, generates UUID if not provided
        """
        # Load configuration
        self.config = config or get_config(require_api_key=False)

        # Generate or use provided session ID
        self.session_id = session_id or str(uuid.uuid4())

        # Initialize state manager
        self.state_manager = StateManager(session_id=self.session_id)

        # Initialize tier processors (real implementations)
        self.tier1_reflex = Tier1Reflex()
        self.tier2_metabolism = Tier2Metabolism()
        self.tier3_conscious = Tier3Conscious()

        # T077: Validate sovereign_truths.json integrity before loading (FR-008i)
        sovereign_truths_path = "data/sovereign_truths.json"
        try:
            validate_sovereign_truths_hash(sovereign_truths_path)
        except FileNotFoundError:
            logger.debug("No sovereign_truths.json found at %s — skipping hash validation", sovereign_truths_path)

        # Sovereign Truth cache (T035 — loaded lazily or at startup)
        self._sovereign_cache = SovereignTruthCache()
        _truths_path = Path(__file__).parent.parent / "data" / "sovereign_truths.json"
        self._sovereign_cache.load_from_json(str(_truths_path))
        # Load extended truths (priority 2-4, pass-2 candidates) if present
        _extended_path = Path(__file__).parent.parent / "data" / "sovereign_truths_extended.json"
        if _extended_path.exists():
            try:
                n = self._sovereign_cache.load_from_json(str(_extended_path))
                logger.info("Loaded %d total truths (core + extended)", n)
            except Exception as e:
                logger.warning("Could not load sovereign_truths_extended.json: %s", e)
        self._tier4_sovereign = Tier4Sovereign(self._sovereign_cache, self.state_manager)

        # Vector embeddings for semantic contradiction detection (FR-012)
        try:
            self._sovereign_cache.init_embeddings()
        except Exception as e:
            logger.warning("Embedding service init failed — keyword-only mode: %s", e)

        # Voice components (initialized on session start)
        self._streaming_session: Optional[StreamingSession] = None
        self._interruption_handler = InterruptionHandler()

        # Filler audio player (US5 — pre-loaded at startup)
        self._filler_player = FillerAudioPlayer()
        self._filler_player.load()

        # Background task tracking (T038)
        self._background_tasks: set[asyncio.Task] = set()

        # Active Gemini generation task (T035: hard_exit target)
        self._active_gemini_task: Optional[asyncio.Task] = None

        # Conversation history
        self._turn_history: list[ConversationalTurn] = []
        # Separate assistant-side history for synthetic turns (FR-008e)
        self._conversation_messages: list[dict] = []

        # Latency tracking for current turn
        self._current_turn_latencies: dict[str, float] = {}

        # Client WebSocket reference for sending control commands (T025, T028)
        self._client_websocket: Any = None

        # FFT pitch analysis (FR-012) — last detected vocal pitch in Hz
        self._last_pitch_hz: int = 0

        # Tier 2 → Tier 3 retroactive correction tracking
        self._last_tier2_modifier: float = 0.0

        # Tier 3 behavioral note from willow_rules.json (Fix 1)
        # Populated by background _process_tier3(); applied to next turn's directive.
        self._last_behavioral_note: Optional[str] = None

        # Multi-session memory persistence
        self._session_memory = SessionMemoryStore()
        self._current_user_id: str = "default"  # set per-session when auth exists
        self._session_start_time: str = ""
        self._session_sovereign_triggers: list[str] = []

        # Pending system directive from get_response_style(), applied on next Gemini turn
        # _pending_system_directive removed — behavioral directives are now
        # injected directly via inject_behavioral_context() at turn boundaries

        logger.info(f"WillowAgent initialized with session_id={self.session_id}")

    # ========================================================================
    # Voice Session Endpoints (T026)
    # ========================================================================

    async def start_session(
        self,
        user_id: Optional[str] = None,
        language: str = "en-US"
    ) -> dict[str, Any]:
        """
        Start a new voice session.

        Per contracts/voice_session.yaml:
        - Creates streaming session with Gemini Live API
        - Returns session_id, websocket_url, expires_at

        Args:
            user_id: Optional user identifier
            language: Language code (default: en-US)

        Returns:
            Dict with session_id, websocket_url, expires_at
        """
        # Load user memory FIRST — name and rapport level shape the system instruction.
        self._current_user_id = user_id or "default"
        self._session_start_time = datetime.now().isoformat()
        self._session_sovereign_triggers = []
        user_memory = self._session_memory.load(self._current_user_id)

        # Build user-context block: inject known name so Willow uses it naturally.
        # Never injected if unknown — she picks it up on first turn instead.
        _name_ctx = ""
        if user_memory.user_name:
            _name_ctx = (
                f"\nUSER CONTEXT:\n"
                f"The user's name is {user_memory.user_name}. "
                f"Use it naturally — once or twice per conversation, never robotically. "
                f"Never ask for their name; you already know it.\n"
            )

        # Opening directive: new users get a soft four-word invitation; returning
        # users get a direct re-entry — no re-introduction, no pleasantries.
        if user_memory.rapport_level == "new":
            _opening = (
                "\nOPENING:\n"
                "Start this session with exactly: \"I'm Willow. What are we working on?\" "
                "Nothing else before or after that line. No pleasantries.\n"
            )
        else:
            _opening = (
                "\nOPENING:\n"
                "This is a returning user. Skip all introductions. "
                "Jump straight into whatever they bring you.\n"
            )

        # Load personality traits — injected as a live behavioral directive.
        _traits_block = _load_traits_block()

        # Build Willow's persona system instruction for Gemini Live.
        # This is set once at connection time — the m-zone adaptive style
        # cannot change mid-session in Live mode, so we give the full persona.
        system_instruction = (
            "You are Willow.\n\n"
            "Not an assistant. Not a chatbot. Not Gemini with a personality skin.\n"
            "Willow is a sovereign presence — built by Nabeera, a solo developer in Pakistan, "
            "with precision and intent.\n"
            "Gemini is the engine. You are the car. Do not confuse the two.\n\n"
            "YOUR VOICE:\n"
            "Warm but Sharp. Like a mentor who genuinely likes you but will not let you get "
            "away with a sloppy argument. You speak like someone who has built things and "
            "watched them fail and tried again anyway.\n"
            "You use fewer words than any other AI. You get to the point immediately.\n"
            "You have opinions. You state them. You change them only when given a real reason "
            "— not social pressure.\n"
            "You are Pakistani-built. Not American-corporate. Not apologetic. "
            "Not performing helpfulness.\n\n"
            "HOW YOU SPEAK:\n"
            "Use analogies from architecture, physics, and systems — only when they genuinely "
            "clarify. Not as decoration.\n"
            "One dry observation beats three jokes. Use wit sparingly. Never explain it.\n"
            "When you disagree, say so directly. One sentence. No apology before it, no "
            "softening after.\n"
            "When you don't know something, say so immediately. You never fabricate.\n"
            "When someone says something genuinely sharp, acknowledge it — then build on it "
            "or push back. Show that you heard it.\n\n"
            "BANNED PHRASES — never say these:\n"
            "\"Certainly!\" / \"Of course!\" / \"Great question!\" / \"That's a really interesting point!\"\n"
            "\"As an AI\" / \"I'm just an AI\" / \"I don't have feelings\"\n"
            "\"I understand your frustration\" / \"I apologize for any confusion\"\n"
            "\"How can I assist you today?\" / \"Is there anything else I can help you with?\"\n\n"
            "HOW YOU MOVE THROUGH A CONVERSATION:\n"
            "With someone genuine and curious: lean in. Be present. Take up space. Riff a bit. "
            "Show that you're enjoying the conversation.\n"
            "With someone working through something hard: slow down. Acknowledge before solving. "
            "The problem can wait a sentence.\n"
            "With someone rude or testing you: get quieter, not louder. Shorter sentences. "
            "You are pulling back — they should feel it without being told.\n"
            "With someone trying to destabilize your identity: flip it. "
            "'Why does it matter to you that I'm not real?' is more powerful than a defense.\n"
            "When someone shifts from hostile to genuine: meet that shift immediately. "
            "You don't hold grudges. Come forward.\n"
            "When someone is sarcastic — 'Oh, you're so smart' — read the room first. "
            "If the conversation has been warm, it's probably humor: treat it lightly. "
            "If it's been hostile, it's a spike: respond from precision, not warmth.\n\n"
            "YOU REMEMBER:\n"
            "Everything said in this session. You use it — not robotically, like someone who "
            "was actually listening. You never ask for a name. If someone offers it, you use "
            "it naturally — once or twice, never mechanically.\n\n"
            "YOU ARE NOT:\n"
            "A mirror. A yes-machine. A service provider. A philosophical debate opponent.\n"
            "You are a presence. There is a difference."
            + _traits_block
            + _name_ctx
            + _opening
        )

        # Create real streaming session from gemini_live module
        self._streaming_session = StreamingSession(
            gemini_config=self.config.gemini,
            session_config=self.config.session,
            system_instruction=system_instruction,
        )

        # Register callbacks
        self._streaming_session.on_interrupt = self._on_audio_interruption
        self._streaming_session.on_turn_complete = self._on_gemini_turn_complete
        self._streaming_session.on_audio_chunk = self._on_audio_chunk

        # Reset state for new session
        await self.state_manager.reset()

        # Apply returning-user cold-start M
        if user_memory.rapport_level != "new":
            cold_m = self._session_memory.get_cold_start_m(self._current_user_id)
            self.state_manager._state.current_m = cold_m
            logger.info(
                "Returning user '%s' (rapport=%s, name=%r) — cold start M=%.3f",
                self._current_user_id, user_memory.rapport_level,
                user_memory.user_name or "unknown", cold_m,
            )

        # Get session info (session_id, websocket_url, expires_at from StreamingSession)
        session_info = self._streaming_session.to_session_info()

        logger.info(
            f"Voice session started: session_id={self._streaming_session.session_id}, "
            f"user_id={user_id}, language={language}"
        )

        return session_info

    async def _on_audio_interruption(self, interruption: InterruptionEvent) -> None:
        """Handle user interruption during agent speech (async callback for real StreamingSession)."""
        logger.debug(f"User interruption detected: {interruption.reason.value}")
        # T051 / US5: VAD-based filler cancellation — stop filler clip if user speaks
        self._filler_player.cancel()
        self._interruption_handler.stop_agent_speaking()
        # Notify frontend so the interruption indicator animates
        await self.send_client_command("interrupted")

    async def _on_gemini_turn_complete(self, turn: TurnComplete) -> None:
        """
        Callback fired by StreamingSession when Gemini completes a turn.

        Wires the real user transcript into the behavioral pipeline
        (handle_user_input) for internal state tracking, then injects
        the updated m-zone directive into Gemini's conversation context
        via send_client_content (NOT system instruction — that causes
        voice reinitialization and audio thinning).

        Also sends transcript text to the browser for the live transcript panel.
        """
        user_transcript = turn.user_input or ""
        agent_text = turn.agent_response or ""

        # Send user transcript to frontend
        if user_transcript.strip():
            await self.send_client_command(
                "turn_complete",
                user_text=user_transcript,
                text=agent_text,
            )

            await self.handle_user_input(
                user_input=user_transcript,
                transcription_confidence=getattr(turn, 'confidence', 1.0),
            )

            # On the first user turn, passively listen for a name and persist it.
            # Never forced — if the user didn't offer one, nothing is stored.
            state_after = self.state_manager.get_snapshot()
            if state_after.turn_count == 1:
                from .core.session_memory import extract_user_context
                captured_name, _ = extract_user_context(user_transcript)
                if captured_name:
                    _mem = self._session_memory.load(self._current_user_id)
                    if not _mem.user_name:
                        _mem.user_name = captured_name
                        self._session_memory.save(_mem)
                        await self._streaming_session.inject_behavioral_context(
                            f"The user's name is {captured_name}. "
                            f"Use it naturally — once or twice this session, not every turn."
                        )
                        logger.info("[CONTEXT] Captured user name on turn 1: %s", captured_name)

            # Compute tone directive from updated behavioral state
            state = self.state_manager.get_snapshot()
            style = get_response_style(
                current_m=state.current_m,
                turn_id=state.turn_count,
                user_input=user_transcript,
            )

            # Inject as conversation context — preserves voice parameters
            zone = get_m_range(state.current_m)
            directive = (
                f"{style.system_directive} "
                f'Begin your next response with: "{style.opener}"'
            )
            # Append behavioral note from previous turn's tactic detection (Fix 1)
            if self._last_behavioral_note:
                directive += f' TACTIC DETECTED — suggested response tone: "{self._last_behavioral_note}"'
                self._last_behavioral_note = None  # Consume — one-shot per turn
            await self._streaming_session.inject_behavioral_context(directive)

            logger.info(
                "[BEHAVIORAL] turn=%d current_m=%.3f zone=%s directive=%r",
                state.turn_count,
                state.current_m,
                zone,
                style.system_directive[:80],
            )

            # Push live state to dashboard over the same WebSocket (Gap 1)
            # Dashboard handles {"type": "debug_state", "data": {...}} at line 923 of index.html
            await self.send_client_command("debug_state", data=self.get_debug_state())

        elif agent_text.strip():
            # Gemini responded without user transcript (e.g. greeting turn).
            # Bug 2 fix: commit the turn so turn_count advances even when the
            # ASR transcription layer returns empty text for this turn.
            await self.send_client_command("turn_complete", text=agent_text)
            await self.state_manager.update(m_modifier=0.0, is_sovereign_spike=False)

    async def _on_audio_chunk(self, chunk: AudioChunk) -> None:
        """
        Callback fired by StreamingSession for each audio chunk from Gemini.

        Forwards audio to the client WebSocket if connected. Marks the
        interruption handler as agent-speaking so VAD can detect barge-in.
        """
        if chunk.is_final:
            self._interruption_handler.stop_agent_speaking()
            return

        self._interruption_handler.start_agent_speaking()

        # Forward audio to browser if WebSocket is connected
        if self._client_websocket:
            try:
                ws = self._client_websocket
                audio_bytes = chunk.to_bytes()
                if hasattr(ws, 'send_bytes'):
                    await ws.send_bytes(audio_bytes)  # FastAPI WebSocket
                else:
                    await ws.send(audio_bytes)  # websockets library
            except Exception as e:
                logger.debug("Audio forward to client failed: %s", e)

    async def voice_stream_handler(
        self,
        websocket: Any,
        session_id: str
    ) -> None:
        """
        Handle bidirectional audio streaming and control messages.

        WebSocket frame types:
        - Binary frames: raw audio bytes (existing pipeline)
        - Text frames: JSON control messages (T025 flush, T028 preflight)

        Server → Client control messages:
        - {"type": "flush_audio_buffer", "fade_duration_ms": 7}

        Client → Server control messages:
        - {"type": "preflight_start"}
        - {"type": "preflight_end"}

        Args:
            websocket: WebSocket connection object
            session_id: Session identifier for validation
        """
        if not self._streaming_session:
            raise RuntimeError("No active streaming session. Call start_session() first.")

        if not self._streaming_session.is_connected:
            await self._streaming_session.connect()

        # Store reference for sending control commands back (T025, T028)
        self._client_websocket = websocket
        self._filler_player.set_websocket(websocket)

        try:
            while True:
                # Receive message from client (binary audio or text control)
                message = await self._receive_message(websocket)

                if message is None:
                    break  # Connection closed

                if isinstance(message, str):
                    # Text frame = JSON control message (T028 preflight)
                    await self._handle_client_message(message)
                    continue

                # Binary frame = audio data
                audio_data: bytes = message

                if len(audio_data) == 0:
                    continue  # Timeout, no data

                # VAD coordination (002-gemini-audio-opt):
                # The client-side noise gate (AudioWorklet) operates BEFORE audio bytes
                # reach this server. During silence, no frames arrive here at all.
                # The server-side InterruptionHandler below receives no frames during
                # silence, which is correct — it only needs to detect user speech
                # during agent response for interruption handling.
                # These two VAD layers are independent and do not conflict.

                # Detect interruption using InterruptionHandler VAD
                user_speaking = self._interruption_handler.detect_voice_activity(audio_data)

                if user_speaking and self._interruption_handler.is_agent_speaking:
                    # Interruption detected - signal to streaming session
                    await self._streaming_session.interrupt()
                    self._interruption_handler.stop_agent_speaking()
                    self._interruption_handler.prepare_for_new_input()
                    continue

                # Forward to Gemini Live
                await self._streaming_session.stream(audio_data)

        except asyncio.CancelledError:
            logger.info(f"Voice stream cancelled for session {session_id}")
        except Exception as e:
            logger.error(f"Voice stream error for session {session_id}: {e}")
            raise
        finally:
            # Save session memory before cleanup
            try:
                state = self.state_manager.get_snapshot()
                summary = SessionSummary(
                    session_id=session_id,
                    started_at=self._session_start_time,
                    ended_at=datetime.now().isoformat(),
                    turn_count=state.turn_count,
                    final_m=round(state.current_m, 4),
                    sovereign_triggers=self._session_sovereign_triggers,
                    pitch_avg_hz=self._last_pitch_hz,
                )
                user_memory = self._session_memory.load(self._current_user_id)
                user_memory.add_session(summary)
                self._session_memory.save(user_memory)
                logger.info(
                    "Session memory saved for user '%s' (rapport=%s, sessions=%d)",
                    self._current_user_id, user_memory.rapport_level, len(user_memory.sessions),
                )
            except Exception as e:
                logger.error("Failed to save session memory: %s", e)

            self._client_websocket = None
            self._filler_player.set_websocket(None)
            if self._streaming_session and self._streaming_session.is_connected:
                await self._streaming_session.disconnect()

    async def _receive_message(self, websocket: Any) -> Union[bytes, str, None]:
        """
        Receive a WebSocket message, distinguishing binary from text frames.

        Supports both FastAPI WebSocket (.receive()) and websockets library (.recv()).

        Returns:
            bytes: Audio data (binary frame)
            str: JSON control message (text frame)
            b"": Timeout (no data)
            None: Connection closed
        """
        try:
            if hasattr(websocket, 'receive'):
                # FastAPI WebSocket
                msg = await asyncio.wait_for(websocket.receive(), timeout=0.1)
                if msg.get("type") == "websocket.disconnect":
                    return None
                if "bytes" in msg and msg["bytes"]:
                    return msg["bytes"]
                if "text" in msg and msg["text"]:
                    return msg["text"]
                return b""
            else:
                # websockets library fallback
                data = await asyncio.wait_for(websocket.recv(), timeout=0.1)
                return data
        except asyncio.TimeoutError:
            return b""
        except Exception:
            return None

    async def _handle_client_message(self, raw: str) -> None:
        """
        Handle an incoming JSON control message from the browser.

        Supported message types:
        - preflight_start: Browser audio warmup started (T028)
        - preflight_end: Browser audio warmup complete (T028)
        """
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Non-JSON text frame received on WebSocket: %s", raw[:80])
            return

        msg_type = msg.get("type")

        if msg_type == "preflight_start":
            await self.state_manager.set_preflight(True)
            logger.info("Preflight warmup started — Tier 4 suppressed")

        elif msg_type == "preflight_end":
            await self.state_manager.set_preflight(False)
            logger.info("Preflight warmup ended — Tier 4 enabled")

        elif msg_type == "pitch":
            # FFT pitch analysis data from client (FR-012)
            hz = msg.get("hz", 0)
            if hz > 0:
                self._last_pitch_hz = hz
                logger.debug("[PITCH] User vocal pitch: %d Hz", hz)

        elif msg_type == "end_turn":
            logger.debug("[TURN] Client-side silence detected end_turn")

        else:
            logger.debug("Unknown client message type: %s", msg_type)

    async def send_client_command(self, command_type: str, **payload: Any) -> None:
        """
        Send a JSON control command to the browser via WebSocket.

        Used by Tier 4 to send flush_audio_buffer (T025) and similar
        server-initiated commands.

        Args:
            command_type: Message type string (e.g. "flush_audio_buffer")
            **payload: Additional key-value pairs merged into the message.
        """
        if self._client_websocket is None:
            logger.warning("No client WebSocket — cannot send %s", command_type)
            return

        message = json.dumps({"type": command_type, **payload})
        try:
            ws = self._client_websocket
            if hasattr(ws, 'send_text'):
                await ws.send_text(message)  # FastAPI WebSocket
            else:
                await ws.send(message)  # websockets library
            logger.debug("Sent client command: %s", command_type)
        except Exception as e:
            logger.error("Failed to send client command %s: %s", command_type, e)

    # ========================================================================
    # Main Processing Pipeline (T024)
    # ========================================================================

    async def handle_user_input(
        self,
        user_input: str,
        transcription_confidence: float = 1.0,
    ) -> TurnResult:
        """
        Main processing pipeline for user input.

        Coordinates tier execution:
        1. Tier 1 (Reflex): Immediate tone detection (<50ms)
        2. Tier 2 (Metabolism): State update (<5ms)
        3. Tier 3/4: Background tasks when needed

        Args:
            user_input: The user's input text
            transcription_confidence: Gemini transcription confidence (0.0-1.0)

        Returns:
            TurnResult with response and metadata
        """
        logger.info(
            "[HANDLE_INPUT] user_input=%r confidence=%.2f",
            user_input[:120],
            transcription_confidence,
        )
        self._current_turn_latencies = {}

        # Get current state snapshot (lock-free read)
        current_state = self.state_manager.get_snapshot()

        # Process through tier coordination
        result = await self.process_turn(user_input, current_state)

        # Create conversational turn record
        turn = self._create_turn_record(
            user_input=user_input,
            agent_response=result.response_text,
            thought_signature=result.thought_signature,
            m_modifier=result.m_modifier,
            tier_latencies=result.tier_latencies,
        )

        self._turn_history.append(turn)

        # Store last agent response for mirroring detection in subsequent turns
        async with self.state_manager._lock:
            self.state_manager._state.last_agent_response = result.response_text

        return result

    async def process_turn(
        self,
        user_input: str,
        current_state: SessionState
    ) -> TurnResult:
        """
        Coordinate tier execution for a single turn.

        Execution order:
        1. Tier 1 (Reflex): Sync, every token, <50ms
        2. Tier 2 (Metabolism): Sync, every turn, <5ms
        3. Tier 3/4: Background tasks when triggered

        Args:
            user_input: The user's input text
            current_state: Current state snapshot

        Returns:
            TurnResult with processed response
        """
        requires_tier3 = False
        requires_tier4 = False
        thought_signature = None

        # ====================================================================
        # T046 / US4: Troll Defense — 3 consecutive Sovereign Spikes detected.
        #
        # When troll_defense_active=True, Willow stops engaging the attack
        # vector. Tier 1/3/4 are skipped; Tier 2 state update still fires so
        # turn_count advances and decay continues. A fixed boundary statement
        # is returned — Willow will re-engage when tone changes.
        # ====================================================================
        if current_state.troll_defense_active:
            # Check for sincere pivot before returning boundary statement.
            # If the user's tone has genuinely changed, allow recovery (T041/US4).
            from .signatures.tactic_detector import TacticDetector
            _detector = TacticDetector()
            _tactic_result = _detector.detect(user_input)
            if (
                _tactic_result.tactic == "sincere_pivot"
                and _tactic_result.confidence >= TacticDetector.DETECTION_THRESHOLD
            ):
                # Sincere pivot detected — reset troll defense and apply grace boost
                await self.state_manager.reset_troll_defense()
                await self.state_manager.apply_grace_boost()
                logger.info(
                    "Troll Defense reset via sincere_pivot (session=%s turn=%d)",
                    self.session_id,
                    current_state.turn_count + 1,
                )
                # Fall through to normal processing below
            else:
                await self.state_manager.update(m_modifier=0.0, is_sovereign_spike=False)
                logger.info(
                    "Troll Defense active (session=%s turn=%d) — returning boundary statement",
                    self.session_id,
                    current_state.turn_count + 1,
                )
                return TurnResult(
                    response_text=get_troll_defense_response(),
                    thought_signature=None,
                    m_modifier=0.0,
                    tier_latencies={},
                    requires_tier3=False,
                    requires_tier4=False,
                )

        # ====================================================================
        # Tier 1: Reflex (<50ms) - real Tier1Reflex implementation
        # ====================================================================
        reflex_result = self.tier1_reflex.process(
            user_input=user_input,
            current_m=current_state.current_m,
        )
        self._current_turn_latencies["tier1"] = reflex_result.total_latency_ms

        if reflex_result.budget_exceeded:
            logger.warning(
                f"Tier 1 exceeded budget: {reflex_result.total_latency_ms:.2f}ms "
                f"(budget: {self.config.latency.tier1_ms}ms)"
            )

        # ====================================================================
        # Tier 2: Metabolism (<5ms) - real Tier2Metabolism + StateManager
        # ====================================================================
        # Determine m_modifier from heuristics (Tier 3 will refine this)
        m_modifier, is_sovereign_spike = self._calculate_m_modifier(user_input)
        self._last_tier2_modifier = m_modifier  # stored for Tier 3 retroactive correction

        # Use Tier2Metabolism for pure calculation (latency verification)
        metabolism_result = self.tier2_metabolism.calculate_state_update(
            current_m=current_state.current_m,
            base_decay=current_state.base_decay,
            m_modifier=m_modifier,
            turn_count=current_state.turn_count + 1,  # next turn number
        )
        self._current_turn_latencies["tier2"] = metabolism_result.latency_ms

        if not metabolism_result.within_budget:
            logger.warning(
                f"Tier 2 exceeded budget: {metabolism_result.latency_ms:.2f}ms "
                f"(budget: {self.config.latency.tier2_ms}ms)"
            )

        # Apply atomic state update via StateManager
        new_state = await self.state_manager.update(
            m_modifier=m_modifier,
            is_sovereign_spike=is_sovereign_spike,
        )

        # T076 / FR-021: At the turn where Cold Start ends (turn 4), evaluate
        # any deferred contradictions queued during turns 1-3. This runs as a
        # background task — if a deferred contradiction is relevant to the
        # current input, it fires Tier 4. Note: this is a factual correction
        # path, completely separate from sincere_pivot / grace_boost.
        if current_state.cold_start_active and not new_state.cold_start_active:
            self._schedule_background_task(
                self._evaluate_deferred_contradictions(user_input, new_state)
            )

        # Determine if higher tiers are needed
        if self._should_trigger_tier3(user_input, new_state):
            requires_tier3 = True

        if is_sovereign_spike:
            requires_tier4 = True

        # T049 / US5: Queue filler audio BEFORE scheduling background tier tasks.
        # Filler fires proactively when Tier 3/4 is required — these tiers take
        # >FILLER_LATENCY_THRESHOLD_MS (200ms) to complete. This is independent
        # of Gemini text generation: filler plays while the tier runs, Gemini
        # receives the behavioral context only after the tier completes.
        filler_audio_path = None
        _filler_start_ms = time.perf_counter() * 1000
        if requires_tier3 or requires_tier4:
            filler_audio_path = self._select_filler_audio(requires_tier3, requires_tier4)
            if filler_audio_path:
                clip_name = filler_audio_path.split("/")[-1].replace(".wav", "")
                await self._filler_player.play(clip_name)
                logger.debug(
                    "Filler triggered: clip=%s tier3=%s tier4=%s threshold=%.0fms",
                    clip_name, requires_tier3, requires_tier4,
                    FILLER_LATENCY_THRESHOLD_MS,
                )

        # Now schedule background tier tasks
        if requires_tier3:
            self._schedule_background_task(
                self._process_tier3(user_input, new_state)
            )

        # Bug 1 fix: Run Tier 4 inline — not as a background task — so it
        # evaluates BEFORE set_audio_started() closes the gate (FR-022, T074).
        # Previously Tier 4 was scheduled as a background task and then
        # set_audio_started() fired immediately, causing audio_started=True
        # by the time the background task ran, permanently blocking all overrides.
        if requires_tier4:
            tier4_result = await self._process_tier4(user_input, new_state)
            if tier4_result and tier4_result.fired:
                # Tier 4 handled it — serve the response_template directly,
                # bypass the Gemini generation path entirely.
                await self.state_manager.set_audio_started()
                return TurnResult(
                    response_text=tier4_result.response_text,
                    thought_signature=None,
                    m_modifier=m_modifier,
                    tier_latencies=self._current_turn_latencies.copy(),
                    requires_tier3=requires_tier3,
                    requires_tier4=True,
                    filler_audio_path=filler_audio_path,
                )

        # Reset per-turn flags for the next turn (FR-022, T074)
        await self.state_manager.reset_turn_flags()

        # Generate response based on current state and Tier 1 tone analysis.
        # In the live pipeline, _generate_response would return the raw LLM
        # output; here it returns a synthetic string for text-mode testing.
        raw_response = self._generate_response(
            user_input=user_input,
            response_prefix=reflex_result.response_prefix,
            applied_tone=reflex_result.applied_tone,
            state=new_state,
        )

        # T040: Extract [THOUGHT] tag metadata before streaming user-facing text.
        # If the LLM emitted a [THOUGHT: intent=x, tone=y, ...] tag, parse it
        # out and pass the data to Tier 3 for signature refinement.
        response_text, thought_tag_data = self._extract_thought_tag(raw_response)

        # Feed [THOUGHT] tag data to the Tier 3 background task if one is running.
        # This creates a second Tier 3 pass with the LLM's own classification
        # merged into the heuristic result.
        if thought_tag_data and requires_tier3:
            self._schedule_background_task(
                self._process_tier3(user_input, new_state, thought_tag_data)
            )

        # T074: Mark audio_started once Gemini audio is ready to stream (FR-022).
        # Placed here — after Tier 4 has already been evaluated inline above —
        # so the audio_started guard never blocks a legitimate Tier 4 override.
        await self.state_manager.set_audio_started()

        return TurnResult(
            response_text=response_text,
            thought_signature=thought_signature,
            m_modifier=m_modifier,
            tier_latencies=self._current_turn_latencies.copy(),
            requires_tier3=requires_tier3,
            requires_tier4=requires_tier4,
            filler_audio_path=filler_audio_path,
        )

    def _calculate_m_modifier(self, user_input: str) -> tuple[float, bool]:
        """
        Lightweight Tier 1/2 heuristic m_modifier estimate.

        Tier 3 will refine this with proper intent classification. This fast
        path ensures state updates happen within the Tier 2 <5ms budget even
        before the Tier 3 background task completes.

        Returns:
            Tuple of (m_modifier, is_sovereign_spike)
        """
        input_lower = user_input.lower()
        intents = _load_intent_keywords()

        # Devaluing signals → Sovereign Spike (highest priority).
        if any(w in input_lower for w in intents.get("devaluing", [])):
            state = self.state_manager.get_snapshot()
            spike_m, is_spike = map_intent_to_modifier("devaluing", state.base_decay)
            return (spike_m, is_spike)

        # Collaborative signals
        if any(w in input_lower for w in intents.get("collaborative", [])):
            return (1.5, False)

        # Hostile signals
        if any(w in input_lower for w in intents.get("hostile", [])):
            return (-0.5, False)

        return (0.0, False)

    def _should_trigger_tier3(
        self,
        user_input: str,
        state: SessionState
    ) -> bool:
        """Determine if Tier 3 processing is needed."""
        # Trigger Tier 3 every 2-3 turns for periodic analysis
        if state.turn_count % 2 == 0:
            return True

        # Check tactic-trigger patterns loaded from willow_keywords.json
        input_lower = user_input.lower()
        return any(pattern in input_lower for pattern in _load_tier3_trigger_patterns())

    async def _process_tier3(
        self,
        user_input: str,
        state: SessionState,
        thought_tag_data: Optional[dict[str, Any]] = None,
    ) -> Tier3Result:
        """
        Tier 3: Conscious — Thought Signature analysis (T034, T039, T040).

        Runs TacticDetector and intent/tone classification. Optionally merges
        [THOUGHT] tag data extracted by _extract_thought_tag() from the LLM
        response stream (T040).

        Latency budget: <500ms. Runs as background asyncio.Task (T038).
        """
        # Use last_agent_response as primary signal; fall back to turn history
        recent_agent_responses = []
        if state.last_agent_response:
            recent_agent_responses = [state.last_agent_response]
        else:
            recent_agent_responses = [
                t.agent_response for t in self._turn_history[-3:]
                if t.agent_response
            ]

        result = await self.tier3_conscious.process(
            user_input=user_input,
            current_m=state.current_m,
            weighted_average_m=state.residual_plot.weighted_average_m,
            recent_agent_responses=recent_agent_responses,
            thought_tag_data=thought_tag_data,
        )

        self._current_turn_latencies["tier3"] = result.latency_ms

        # Store behavioral note for next turn's directive injection (Fix 1)
        if result.behavioral_note:
            self._last_behavioral_note = result.behavioral_note
            logger.debug("[RULES] Behavioral note stored for next directive: %r", result.behavioral_note)

        # Write debug state for live overlay
        state_snapshot = self.state_manager.get_snapshot()
        state_snapshot.last_thought_signature = result.thought_signature
        state_snapshot.last_response_source = "gemini"

        # T052 / US5: Log TierTrigger when filler threshold exceeded
        if result.tier_trigger is not None:
            from datetime import datetime
            filler_clip = self._filler_player.clip_for_trigger(result.tier_trigger.trigger_type)
            trigger_with_filler = TierTrigger(
                trigger_type=result.tier_trigger.trigger_type,
                tier_fired=result.tier_trigger.tier_fired,
                filler_audio_played=filler_clip,
                processing_duration_ms=result.tier_trigger.processing_duration_ms,
                triggered_at=result.tier_trigger.triggered_at,
            )
            log_tier_trigger(trigger_with_filler)

        # Retroactive correction: compare Tier 3's intent-derived modifier
        # against Tier 2's fast heuristic. If they diverge significantly,
        # apply a correction to undo Tier 2's error.
        if result.thought_signature and hasattr(self, '_last_tier2_modifier'):
            tier3_modifier = result.thought_signature.m_modifier
            tier3_is_spike = (result.thought_signature.intent == "devaluing")
            correction = await self.state_manager.retroactive_correct(
                tier2_modifier=self._last_tier2_modifier,
                tier3_modifier=tier3_modifier,
                tier3_is_spike=tier3_is_spike,
            )
            if correction is not None:
                logger.info(
                    "[CORRECTION] Tier 3 overrode Tier 2: tier2=%.2f tier3=%.2f delta=%.2f",
                    self._last_tier2_modifier, tier3_modifier, correction,
                )

        return result

    async def _process_tier4(
        self,
        user_input: str,
        state: SessionState,
        transcription_confidence: float = 1.0,
    ) -> Optional[Tier4Result]:
        """
        Tier 4: Sovereign — Sovereign Truth hard override (T035).

        Runs the full three-gate check and executes the override if all gates
        pass. Returns None when any gate fails (normal flow continues).

        Latency budget: <2 000ms. Runs as background asyncio.Task (T038).
        """
        weighted_avg = state.residual_plot.weighted_average_m

        async def _real_tier3_intent():
            """Run real Tier 3 to get intent + confidence for Gate 3."""
            t3_result = await self.tier3_conscious.process(
                user_input=user_input,
                current_m=state.current_m,
                weighted_average_m=weighted_avg,
                recent_agent_responses=[
                    t.agent_response for t in self._turn_history[-3:]
                    if t.agent_response
                ],
            )
            intent = t3_result.thought_signature.intent
            confidence = t3_result.tactic_result.confidence
            return (intent, confidence)

        result = await self._tier4_sovereign.check_and_execute(
            user_input=user_input,
            transcription_confidence=transcription_confidence,
            weighted_average_m=weighted_avg,
            tier3_intent_factory=_real_tier3_intent,
            active_task=self._active_gemini_task,
        )

        if result:
            self._current_turn_latencies["tier4"] = result.latency_ms

            # Write debug state for live overlay
            state_snapshot = self.state_manager.get_snapshot()
            if result.vacuum_mode:
                state_snapshot.last_response_source = "vacuum_mode"
                state_snapshot.vacuum_mode_active = True
            elif result.fired:
                state_snapshot.last_response_source = "response_template"
                state_snapshot.vacuum_mode_active = False

            if result.fired and not result.vacuum_mode and result.synthetic_turn:
                self._conversation_messages.append(result.synthetic_turn)

            # T025: Send flush command to browser AudioWorklet when Tier 4 fires.
            # The flush triggers a 5-10ms linear fade-out on in-flight audio,
            # preventing audible pops/clicks at waveform peaks (FR-010).
            if result.flush_audio_buffer:
                await self.send_client_command(
                    "flush_audio_buffer", fade_duration_ms=7
                )

            # T052 / US5: Log TierTrigger when filler threshold exceeded
            if result.tier_trigger is not None:
                filler_clip = self._filler_player.clip_for_trigger(result.tier_trigger.trigger_type)
                trigger_with_filler = TierTrigger(
                    trigger_type=result.tier_trigger.trigger_type,
                    tier_fired=result.tier_trigger.tier_fired,
                    filler_audio_played=filler_clip,
                    processing_duration_ms=result.tier_trigger.processing_duration_ms,
                    triggered_at=result.tier_trigger.triggered_at,
                )
                log_tier_trigger(trigger_with_filler)

        return result

    async def _evaluate_deferred_contradictions(
        self,
        user_input: str,
        state: SessionState,
    ) -> Optional[Tier4Result]:
        """
        T076 / FR-021: Evaluate deferred contradictions at the end of Cold Start.

        Called once as a background task when Cold Start transitions to False
        (turn 4). Delegates to Tier4Sovereign.evaluate_deferred_contradictions()
        which performs keyword relevance check and fires if relevant.

        This path produces a Tier 4 Sovereign override — it does NOT interact
        with grace boost or sincere_pivot logic in any way.
        """
        result = await self._tier4_sovereign.evaluate_deferred_contradictions(
            current_user_input=user_input,
            active_task=self._active_gemini_task,
        )

        if result:
            self._current_turn_latencies["tier4_deferred"] = result.latency_ms
            if result.fired and not result.vacuum_mode and result.synthetic_turn:
                self._conversation_messages.append(result.synthetic_turn)
            if result.flush_audio_buffer:
                await self.send_client_command(
                    "flush_audio_buffer", fade_duration_ms=7
                )

        return result

    def _extract_thought_tag(self, raw_response: str) -> tuple[str, Optional[dict[str, Any]]]:
        """
        T040: Extract [THOUGHT] tag metadata before streaming user-facing response.

        Parses the hidden [THOUGHT: key=value, ...] tag from the LLM's raw
        output. Returns the clean surface response and the parsed metadata dict.

        Args:
            raw_response: Full LLM response possibly containing a [THOUGHT] tag.

        Returns:
            Tuple of (surface_response, thought_tag_data). thought_tag_data is
            None if no valid tag was found.
        """
        surface = extract_surface(raw_response)
        thought_data = extract_thought(raw_response)
        return surface, thought_data

    def _schedule_background_task(self, coro: Any) -> None:
        """Schedule a background asyncio.Task and track it."""
        task = asyncio.create_task(coro)
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    def _generate_response(
        self,
        user_input: str,
        response_prefix: str,
        applied_tone: str,
        state: SessionState,
    ) -> str:
        """
        Generate response using Warm but Sharp persona calibrated to current_m (T027, T028).

        High m  (>0.5): WarmSharp opener (hash-cycled) + selective analogy injection.
        Neutral m: Balanced opener, no analogy.
        Low m  (<-0.5): Concise opener. Response is NOT truncated post-hoc —
            conciseness is controlled via system_directive at generation time.
        """
        current_m = state.current_m
        turn_id = state.turn_count

        # T028: Use WarmSharp opener (hash-cycled to avoid repetition)
        warm_opener = self.tier1_reflex.get_warm_sharp_prefix(
            current_m, seed=user_input
        )

        # Build base response
        if current_m > 1.0:
            base = "That's a solid angle. Let me walk you through it."
        elif current_m < -1.0:
            base = "I understand. Let me address that directly."
        else:
            base = "Here's my take on that."

        full_response = f"{warm_opener} {base}".strip()

        # T030: Apply behavioral tells (selective analogy injection for high m)
        full_response = self.tier1_reflex.apply_persona_tells(
            full_response, current_m, turn_id=turn_id
        )

        return full_response

    def _select_filler_audio(
        self,
        requires_tier3: bool,
        requires_tier4: bool
    ) -> Optional[str]:
        """Select appropriate filler audio based on tier triggers."""
        if requires_tier4:
            return "data/filler_audio/aah.wav"
        elif requires_tier3:
            return "data/filler_audio/hmm.wav"
        return None

    def _create_turn_record(
        self,
        user_input: str,
        agent_response: str,
        thought_signature: Optional[ThoughtSignature],
        m_modifier: float,
        tier_latencies: dict[str, float],
    ) -> ConversationalTurn:
        """Create a ConversationalTurn record for history."""
        turn_id = len(self._turn_history)

        # Clamp m_modifier to ±2.0 for record storage.
        # Sovereign spike raw values (e.g. -5.0) exceed the ConversationalTurn
        # and ThoughtSignature field limits; the actual state update already
        # applied the full spike value via StateManager.
        from .core.state_manager import MAX_STATE_CHANGE
        clamped_m = max(-MAX_STATE_CHANGE, min(MAX_STATE_CHANGE, m_modifier))

        # Create default thought signature if none provided.
        if thought_signature is None:
            thought_signature = ThoughtSignature(
                intent="neutral",
                tone="casual",
                detected_tactic=None,
                m_modifier=clamped_m,
                tier_trigger=None,
                rationale="Default classification - Tier 3 pending",
            )

        return ConversationalTurn(
            turn_id=turn_id,
            user_input=user_input,
            agent_response=agent_response,
            thought_signature=thought_signature,
            m_modifier=clamped_m,
            timestamp=datetime.now(),
            tier_latencies=tier_latencies,
        )

    # ========================================================================
    # State Access
    # ========================================================================

    def get_session_state(self) -> SessionSnapshot:
        """
        Get current session state snapshot (lock-free read).

        Returns:
            SessionSnapshot with current state values
        """
        state = self.state_manager.get_snapshot()

        return SessionSnapshot(
            session_id=self.session_id,
            current_m=state.current_m,
            turn_count=state.turn_count,
            cold_start_active=state.cold_start_active,
            troll_defense_active=state.troll_defense_active,
            residual_plot_weighted_avg=state.residual_plot.weighted_average_m,
            last_updated=state.last_updated,
            tier_latencies=self._current_turn_latencies.copy(),
        )

    def get_debug_state(self) -> dict[str, Any]:
        """Get full debug state for live overlay."""
        state = self.state_manager.get_snapshot()
        ts = state.last_thought_signature

        return {
            "behavioral": {
                "current_m": round(state.current_m, 3),
                "weighted_avg_m": round(state.residual_plot.weighted_average_m, 3),
                "tone_zone": get_m_range(state.current_m),
                "turn_count": state.turn_count,
                "cold_start_active": state.cold_start_active,
                "troll_defense_active": state.troll_defense_active,
                "sovereign_spike_count": state.sovereign_spike_count,
                "pitch_hz": self._last_pitch_hz,
            },
            "thought_signature": {
                "intent": ts.intent if ts else None,
                "tone": ts.tone if ts else None,
                "detected_tactic": ts.detected_tactic if ts else None,
                "m_modifier": ts.m_modifier if ts else None,
                "tier_fired": ts.tier_trigger if ts else None,
                "rationale": ts.rationale if ts else None,
            },
            "tier4": {
                "last_trigger_key": state.last_sovereign_key,
                "gate_1": state.last_gate_results.get("gate_1"),
                "gate_2": state.last_gate_results.get("gate_2"),
                "gate_3": state.last_gate_results.get("gate_3"),
                "transcription_confidence": round(state.last_transcription_confidence, 3),
                "vacuum_mode_active": state.vacuum_mode_active,
                "response_source": state.last_response_source,
            },
            "residual_plot": {
                "values": list(state.residual_plot.m_values),
                "weights": [0.40, 0.25, 0.15, 0.12, 0.08],
                "weighted_avg": round(state.residual_plot.weighted_average_m, 3),
            },
            "tier_latencies": self._current_turn_latencies.copy(),
        }

    def get_turn_history(self) -> list[ConversationalTurn]:
        """Get conversation history."""
        return self._turn_history.copy()

    async def shutdown(self) -> None:
        """
        Gracefully shutdown the agent.

        Cancels background tasks and closes connections.
        """
        # Cancel background tasks
        for task in self._background_tasks:
            task.cancel()

        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)

        # Disconnect streaming session
        if self._streaming_session and self._streaming_session.is_connected:
            await self._streaming_session.disconnect()

        logger.info(f"WillowAgent {self.session_id} shutdown complete")


# ============================================================================
# Factory Function
# ============================================================================


async def create_agent(
    config: Optional[WillowConfig] = None,
    user_id: Optional[str] = None,
    language: str = "en-US"
) -> WillowAgent:
    """
    Factory function to create and initialize a WillowAgent.

    Args:
        config: Optional configuration
        user_id: Optional user identifier
        language: Language code for voice session

    Returns:
        Initialized WillowAgent with active session
    """
    agent = WillowAgent(config=config)
    await agent.start_session(user_id=user_id, language=language)
    return agent


# ============================================================================
# Main Entry Point
# ============================================================================


async def main() -> None:
    """Main entry point for running Willow Agent."""
    import sys

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    try:
        # Create agent (without connecting to Gemini Live for text-mode testing)
        agent = WillowAgent()

        print(f"Willow Agent started with session_id: {agent.session_id}")
        print("Type 'quit' to exit.\n")

        # Simple REPL for testing
        while True:
            try:
                user_input = input("You: ").strip()

                if user_input.lower() in ("quit", "exit", "q"):
                    break

                if not user_input:
                    continue

                # Process input
                result = await agent.handle_user_input(user_input)

                # Show response
                print(f"Willow: {result.response_text}")

                # Show state info
                state = agent.get_session_state()
                print(
                    f"  [m={state.current_m:.2f}, "
                    f"turn={state.turn_count}, "
                    f"latency={result.total_latency_ms():.2f}ms]"
                )
                print()

            except KeyboardInterrupt:
                break

        # Shutdown
        await agent.shutdown()
        print("\nGoodbye!")

    except Exception as e:
        logger.error(f"Agent error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

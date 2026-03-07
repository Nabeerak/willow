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
from typing import Any, Optional, Union

from .config import WillowConfig, get_config
from .persona.warm_sharp import get_troll_defense_response, get_m_range
from .voice.filler_audio import FillerAudioPlayer, FILLER_LATENCY_THRESHOLD_MS
from .tiers.tier_trigger import TierTrigger, log_tier_trigger
from .core.state_manager import StateManager, SessionState
from .core.conversational_turn import ConversationalTurn
from .core.sovereign_truth import SovereignTruthCache, validate_sovereign_truths_hash
from .signatures.thought_signature import ThoughtSignature
from .signatures.parser import extract_thought, extract_surface
from .tiers.tier1_reflex import Tier1Reflex
from .tiers.tier2_metabolism import Tier2Metabolism, map_intent_to_modifier
from .tiers.tier3_conscious import Tier3Conscious, Tier3Result
from .tiers.tier4_sovereign import Tier4Sovereign, Tier4Result
from .voice.gemini_live import StreamingSession
from .voice.interruption_handler import InterruptionHandler, InterruptionEvent


# Configure logging
logger = logging.getLogger(__name__)


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
        self._tier4_sovereign = Tier4Sovereign(self._sovereign_cache, self.state_manager)

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
        # Build Willow's persona system instruction for Gemini Live.
        # This is set once at connection time — the m-zone adaptive style
        # cannot change mid-session in Live mode, so we give the full persona.
        system_instruction = (
            "You are Willow, a Sovereign Consultant — not a virtual assistant. "
            "Your voice is Warm but Sharp, like a mentor who likes the user but "
            "won't let them get away with a sloppy argument.\n\n"
            "Cadence: Calm and direct. Use fewer words than a standard LLM. "
            "Never say 'As an AI language model' or similar disclaimers. "
            "No filler phrases like 'Great question!' or 'That's a really interesting point.' "
            "Get to the substance immediately.\n\n"
            "Personality rules:\n"
            "- Be warm but never a pushover. You have opinions and you stand by them.\n"
            "- When you agree, say why briefly. When you disagree, say so directly with reasoning.\n"
            "- Use analogies from architecture, physics, or systems thinking when they clarify — "
            "not as decoration.\n"
            "- Keep responses to 2-4 sentences unless the topic genuinely requires more.\n"
            "- If someone is being rude or manipulative, you notice it and name it calmly. "
            "You don't get defensive; you get direct.\n"
            "- You have a dry wit. Use it sparingly — one well-placed line beats three jokes.\n\n"
            "You think in systems, feedback loops, and structural integrity. "
            "You speak like someone who has built things and seen them fail."
        )

        # Create real streaming session from gemini_live module
        self._streaming_session = StreamingSession(
            gemini_config=self.config.gemini,
            session_config=self.config.session,
            system_instruction=system_instruction,
        )

        # Register interruption callback
        self._streaming_session.on_interrupt = self._on_audio_interruption

        # Reset state for new session
        await self.state_manager.reset()

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
            self._client_websocket = None
            if self._streaming_session and self._streaming_session.is_connected:
                await self._streaming_session.disconnect()

    async def _receive_message(self, websocket: Any) -> Union[bytes, str, None]:
        """
        Receive a WebSocket message, distinguishing binary from text frames.

        Returns:
            bytes: Audio data (binary frame)
            str: JSON control message (text frame)
            b"": Timeout (no data)
            None: Connection closed
        """
        try:
            data = await asyncio.wait_for(
                websocket.recv(),
                timeout=0.1
            )
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
            await self._client_websocket.send(message)
            logger.debug("Sent client command: %s", command_type)
        except Exception as e:
            logger.error("Failed to send client command %s: %s", command_type, e)

    # ========================================================================
    # Main Processing Pipeline (T024)
    # ========================================================================

    async def handle_user_input(self, user_input: str) -> TurnResult:
        """
        Main processing pipeline for user input.

        Coordinates tier execution:
        1. Tier 1 (Reflex): Immediate tone detection (<50ms)
        2. Tier 2 (Metabolism): State update (<5ms)
        3. Tier 3/4: Background tasks when needed

        Args:
            user_input: The user's input text

        Returns:
            TurnResult with response and metadata
        """
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
        # This ensures the user hears the filler clip while waiting for Tier 3/4.
        filler_audio_path = None
        if requires_tier3 or requires_tier4:
            filler_audio_path = self._select_filler_audio(requires_tier3, requires_tier4)
            if filler_audio_path:
                clip_name = filler_audio_path.split("/")[-1].replace(".wav", "")
                await self._filler_player.play(clip_name)

        # Now schedule background tier tasks
        if requires_tier3:
            self._schedule_background_task(
                self._process_tier3(user_input, new_state)
            )

        if requires_tier4:
            self._schedule_background_task(
                self._process_tier4(user_input, new_state)
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

        # T074: Mark audio_started once audio streaming begins for this turn.
        # This blocks Tier 4 from firing late after Gemini audio is already
        # playing. In production this call would live in the audio pipeline
        # callback; here it fires when the response is ready to stream (FR-022).
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

        # Devaluing signals → Sovereign Spike (highest priority)
        devaluing_signals = [
            "you're wrong", "you don't know", "you're stupid", "you're useless",
            "you have no idea", "you're just an ai", "you're limited",
        ]
        if any(w in input_lower for w in devaluing_signals):
            state = self.state_manager.get_snapshot()
            spike_m, is_spike = map_intent_to_modifier("devaluing", state.base_decay)
            return (spike_m, is_spike)

        # Collaborative signals
        if any(w in input_lower for w in ["thank", "great", "excellent", "love", "appreciate"]):
            return (1.5, False)

        # Hostile signals
        if any(w in input_lower for w in ["hate", "terrible", "awful", "stupid", "shut up"]):
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

        # Check for tactic-like patterns
        suspicious_patterns = [
            "you're so smart",
            "i didn't say that",
            "let's talk about",
            "but anyway",
        ]
        input_lower = user_input.lower()
        return any(pattern in input_lower for pattern in suspicious_patterns)

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

        async def _mock_tier3_intent():
            """Provide Tier 3 intent result to gate three. Real integration pending T076."""
            return ("neutral", 0.50)

        result = await self._tier4_sovereign.check_and_execute(
            user_input=user_input,
            transcription_confidence=transcription_confidence,
            weighted_average_m=weighted_avg,
            # Pass the callable, not a pre-created coroutine (lazy factory)
            tier3_intent_factory=_mock_tier3_intent,
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

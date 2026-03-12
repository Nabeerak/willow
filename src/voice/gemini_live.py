"""
Gemini Live API WebSocket Connection

Implements real-time voice streaming with Gemini Live API for the Willow Behavioral
Framework. Provides bidirectional audio streaming with interruption support as
specified in contracts/voice_session.yaml.

Part of User Story 1: Natural Voice Conversation (Priority: P1)
Task T018: Implement Gemini Live API WebSocket connection

Audio Format: 16kHz, 16-bit PCM, mono (per voice_session.yaml)
"""

import asyncio
import base64
import json
import logging
import uuid
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Awaitable, Callable

from google import genai
from google.genai import types as genai_types

from ..config import GeminiConfig, SessionConfig, get_config

logger = logging.getLogger(__name__)


# Audio format constants per voice_session.yaml
AUDIO_SAMPLE_RATE_HZ = 16000
AUDIO_BITS_PER_SAMPLE = 16
AUDIO_CHANNELS = 1


class SessionState(Enum):
    """State machine for streaming session lifecycle."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    STREAMING = "streaming"
    INTERRUPTED = "interrupted"
    CLOSING = "closing"
    ERROR = "error"


class InterruptionReason(Enum):
    """Reasons for stream interruption per voice_session.yaml."""
    USER_SPEECH_DETECTED = "user_speech_detected"
    SILENCE_TIMEOUT = "silence_timeout"


@dataclass(frozen=True)
class AudioChunk:
    """
    Audio chunk for streaming per voice_session.yaml schema.

    Attributes:
        type: Message type identifier (always "audio_chunk")
        audio_data: Base64-encoded audio (16kHz, 16-bit PCM, mono)
        chunk_index: Sequential chunk number for ordering
        is_final: True if this is the last chunk of a turn
    """
    type: str = field(default="audio_chunk", init=False)
    audio_data: str
    chunk_index: int
    is_final: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "type": self.type,
            "audio_data": self.audio_data,
            "chunk_index": self.chunk_index,
            "is_final": self.is_final
        }

    @classmethod
    def from_bytes(cls, audio_bytes: bytes, chunk_index: int, is_final: bool = False) -> "AudioChunk":
        """
        Create AudioChunk from raw PCM bytes.

        Args:
            audio_bytes: Raw 16kHz, 16-bit PCM, mono audio data
            chunk_index: Sequential chunk number
            is_final: Whether this is the last chunk of a turn

        Returns:
            AudioChunk with base64-encoded audio data
        """
        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
        return cls(audio_data=audio_b64, chunk_index=chunk_index, is_final=is_final)

    def to_bytes(self) -> bytes:
        """Decode base64 audio data to raw PCM bytes."""
        return base64.b64decode(self.audio_data)


@dataclass(frozen=True)
class Interruption:
    """
    Interruption event per voice_session.yaml schema.

    Attributes:
        type: Message type identifier (always "interruption")
        interrupted_at_chunk: Which agent response chunk was interrupted
        reason: Why the interruption occurred
    """
    type: str = field(default="interruption", init=False)
    interrupted_at_chunk: int
    reason: InterruptionReason

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "type": self.type,
            "interrupted_at_chunk": self.interrupted_at_chunk,
            "reason": self.reason.value
        }


@dataclass(frozen=True)
class TurnComplete:
    """
    Turn completion event per voice_session.yaml schema.

    Attributes:
        type: Message type identifier (always "turn_complete")
        turn_id: Sequential turn identifier
        user_input: Transcribed user speech
        agent_response: Surface text (excludes [THOUGHT] tags)
        m_modifier: Feedback modifier applied this turn
        tier_latencies: Processing time per tier in milliseconds
    """
    type: str = field(default="turn_complete", init=False)
    turn_id: int
    user_input: str
    agent_response: str
    m_modifier: float
    tier_latencies: dict[str, float]

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "type": self.type,
            "turn_id": self.turn_id,
            "user_input": self.user_input,
            "agent_response": self.agent_response,
            "m_modifier": self.m_modifier,
            "tier_latencies": self.tier_latencies
        }


# Callback type aliases for clarity
OnAudioChunkCallback = Callable[[AudioChunk], Awaitable[None]]
OnInterruptCallback = Callable[[Interruption], Awaitable[None]]
OnTurnCompleteCallback = Callable[[TurnComplete], Awaitable[None]]


class StreamingSessionError(Exception):
    """Base exception for streaming session errors."""
    pass


class ConnectionError(StreamingSessionError):
    """Raised when connection to Gemini Live API fails."""
    pass


class SessionExpiredError(StreamingSessionError):
    """Raised when session has expired."""
    pass


class StreamingSession:
    """
    Manages WebSocket connection to Gemini Live API for real-time voice streaming.

    Implements bidirectional audio streaming with interruption support as specified
    in contracts/voice_session.yaml.

    Audio Format: 16kHz, 16-bit PCM, mono

    Attributes:
        session_id: Unique session identifier
        websocket_url: URL for WebSocket connection
        expires_at: Session expiration timestamp
        state: Current session state

    Callbacks:
        on_audio_chunk: Called when audio chunk is received from Gemini
        on_interrupt: Called when interruption event occurs
        on_turn_complete: Called when a conversational turn completes

    Example:
        >>> session = StreamingSession()
        >>> session.on_audio_chunk = my_audio_handler
        >>> session.on_interrupt = my_interrupt_handler
        >>> session.on_turn_complete = my_turn_handler
        >>> await session.connect()
        >>> await session.stream(audio_bytes)
        >>> await session.disconnect()
    """

    def __init__(
        self,
        gemini_config: GeminiConfig | None = None,
        session_config: SessionConfig | None = None,
        model_id: str | None = None,
        auto_vad: bool = True,
        system_instruction: str | None = None,
    ) -> None:
        """
        Initialize StreamingSession.

        Args:
            gemini_config: Gemini API configuration (defaults to environment config)
            session_config: Session configuration (defaults to environment config)
            model_id: Gemini model identifier for Live API (defaults to GeminiConfig.model_id)
            auto_vad: If True (default), Gemini auto-detects speech boundaries.
                      If False, caller must use activity_start/activity_end signals.
            system_instruction: System prompt for Gemini Live persona. If None,
                no system instruction is sent (generic AI behavior).
        """
        config = get_config(require_api_key=False)
        self._gemini_config = gemini_config or config.gemini
        self._session_config = session_config or config.session
        self._model_id = model_id or self._gemini_config.model_id
        self._auto_vad = auto_vad
        self._system_instruction = system_instruction

        # Session identifiers
        self.session_id: str = str(uuid.uuid4())
        self.websocket_url: str = f"wss://willow.run.app/api/v1/session/{self.session_id}/stream"
        self.expires_at: datetime = datetime.now(timezone.utc) + timedelta(
            seconds=self._session_config.timeout_seconds
        )

        # Session state
        self._state: SessionState = SessionState.DISCONNECTED
        self._client: genai.Client | None = None
        self._live_session: genai_types.AsyncSession | None = None
        self._exit_stack: AsyncExitStack | None = None

        # Turn tracking
        self._current_turn_id: int = 0
        self._current_chunk_index: int = 0
        self._accumulated_user_input: str = ""
        self._accumulated_agent_response: str = ""
        self._turn_complete_fired: bool = False  # tracks late transcription
        self._activity_started: bool = False

        # Tier latency tracking per turn
        self._tier_latencies: dict[str, float] = {}

        # Callbacks
        self._on_audio_chunk: OnAudioChunkCallback | None = None
        self._on_interrupt: OnInterruptCallback | None = None
        self._on_turn_complete: OnTurnCompleteCallback | None = None

        # Session timing
        self._session_started_at: datetime | None = None

        # Asyncio primitives
        self._receive_task: asyncio.Task | None = None
        self._duration_log_task: asyncio.Task | None = None
        self._stream_lock: asyncio.Lock = asyncio.Lock()
        self._shutdown_event: asyncio.Event = asyncio.Event()

    @property
    def state(self) -> SessionState:
        """Get current session state."""
        return self._state

    @property
    def on_audio_chunk(self) -> OnAudioChunkCallback | None:
        """Get audio chunk callback."""
        return self._on_audio_chunk

    @on_audio_chunk.setter
    def on_audio_chunk(self, callback: OnAudioChunkCallback | None) -> None:
        """Set audio chunk callback."""
        self._on_audio_chunk = callback

    @property
    def on_interrupt(self) -> OnInterruptCallback | None:
        """Get interruption callback."""
        return self._on_interrupt

    @on_interrupt.setter
    def on_interrupt(self, callback: OnInterruptCallback | None) -> None:
        """Set interruption callback."""
        self._on_interrupt = callback

    @property
    def on_turn_complete(self) -> OnTurnCompleteCallback | None:
        """Get turn complete callback."""
        return self._on_turn_complete

    @on_turn_complete.setter
    def on_turn_complete(self, callback: OnTurnCompleteCallback | None) -> None:
        """Set turn complete callback."""
        self._on_turn_complete = callback

    @property
    def is_connected(self) -> bool:
        """Check if session is connected and active."""
        return self._state in (SessionState.CONNECTED, SessionState.STREAMING)

    @property
    def is_expired(self) -> bool:
        """Check if session has expired."""
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def session_duration_seconds(self) -> float:
        """Get session duration in seconds since connect(), or 0.0 if not connected."""
        if self._session_started_at and self.is_connected:
            return (datetime.now(timezone.utc) - self._session_started_at).total_seconds()
        return 0.0

    async def connect(self) -> None:
        """
        Establish connection to Gemini Live API.

        Creates the Gemini client and opens a live session for bidirectional
        audio streaming.

        Raises:
            ConnectionError: If connection fails
            SessionExpiredError: If session has expired
            ValueError: If API key is not configured
        """
        if self.is_expired:
            raise SessionExpiredError(f"Session {self.session_id} has expired")

        if self._state != SessionState.DISCONNECTED:
            raise StreamingSessionError(
                f"Session {self.session_id} cannot connect: already in state "
                f"{self._state.value}. Disconnect first to avoid double-connect."
            )

        self._state = SessionState.CONNECTING
        logger.info(f"Connecting session {self.session_id}")

        try:
            # Validate API key
            self._gemini_config.validate()

            # Create Gemini client
            self._client = genai.Client(api_key=self._gemini_config.api_key)

            # Configure live session for audio streaming with thinking support.
            live_config_kwargs = dict(
                response_modalities=["AUDIO"],
                thinking_config=genai_types.ThinkingConfig(
                    thinking_level=genai_types.ThinkingLevel.MINIMAL,
                    include_thoughts=True,
                ),
                speech_config=genai_types.SpeechConfig(
                    voice_config=genai_types.VoiceConfig(
                        prebuilt_voice_config=genai_types.PrebuiltVoiceConfig(
                            voice_name=self._gemini_config.voice_name
                        )
                    )
                ),
            )
            # Enable transcription for both input (user speech) and output (agent speech)
            # so on_turn_complete receives real transcript text for the dashboard
            try:
                live_config_kwargs["input_audio_transcription"] = genai_types.InputAudioTranscription()
                live_config_kwargs["output_audio_transcription"] = genai_types.AudioTranscriptionConfig()
            except (AttributeError, TypeError):
                logger.warning("[GEMINI] Audio transcription config not available in this SDK version")

            # Inject persona system instruction if provided
            if self._system_instruction:
                live_config_kwargs["system_instruction"] = self._system_instruction
            # Manual VAD: browser noise gate handles silence detection;
            # Python layer controls turn boundaries via activity_start/end.
            # Auto VAD (default): Gemini detects speech pauses automatically.
            if not self._auto_vad:
                live_config_kwargs["realtime_input_config"] = genai_types.RealtimeInputConfig(
                    automatic_activity_detection=genai_types.AutomaticActivityDetection(
                        disabled=True
                    )
                )
            live_config = genai_types.LiveConnectConfig(**live_config_kwargs)

            # live.connect() is an async context manager, not a coroutine
            # Use AsyncExitStack to enter it and keep the connection alive
            self._exit_stack = AsyncExitStack()
            self._live_session = await self._exit_stack.enter_async_context(
                self._client.aio.live.connect(
                    model=self._model_id,
                    config=live_config
                )
            )

            self._state = SessionState.CONNECTED
            self._session_started_at = datetime.now(timezone.utc)
            logger.info(f"Session {self.session_id} connected successfully")

            # Start background receive task
            self._receive_task = asyncio.create_task(self._receive_loop())

            # Start session duration logger (logs every 5 minutes)
            self._duration_log_task = asyncio.create_task(self._duration_log_loop())

        except ValueError as e:
            self._state = SessionState.ERROR
            logger.error(f"Session {self.session_id} configuration error: {e}")
            raise
        except Exception as e:
            self._state = SessionState.ERROR
            logger.error(f"Session {self.session_id} connection failed: {e}")
            raise ConnectionError(f"Failed to connect to Gemini Live API: {e}") from e

    async def disconnect(self) -> None:
        """
        Close connection to Gemini Live API.

        Gracefully shuts down the streaming session and cleans up resources.
        """
        if self._state == SessionState.DISCONNECTED:
            return

        self._state = SessionState.CLOSING
        logger.info(f"Disconnecting session {self.session_id}")

        # Signal shutdown to receive loop
        self._shutdown_event.set()

        # Cancel receive task
        if self._receive_task and not self._receive_task.done():
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass

        # Cancel duration log task
        if self._duration_log_task and not self._duration_log_task.done():
            self._duration_log_task.cancel()
            try:
                await self._duration_log_task
            except asyncio.CancelledError:
                pass

        # Close live session via exit stack (proper context manager teardown)
        if self._exit_stack:
            try:
                await self._exit_stack.aclose()
            except Exception as e:
                logger.warning(f"Error closing live session: {e}")
            self._exit_stack = None
        self._live_session = None

        self._client = None
        self._state = SessionState.DISCONNECTED
        logger.info(f"Session {self.session_id} disconnected")

    async def stream(self, audio_data: bytes) -> None:
        """
        Stream audio data to Gemini Live API.

        Sends raw PCM audio data for processing by the Gemini model.
        Audio responses are received asynchronously via the on_audio_chunk callback.

        Args:
            audio_data: Raw 16kHz, 16-bit PCM, mono audio data

        Raises:
            StreamingSessionError: If session is not connected
            SessionExpiredError: If session has expired
        """
        if self.is_expired:
            raise SessionExpiredError(f"Session {self.session_id} has expired")

        if not self.is_connected:
            raise StreamingSessionError(
                f"Cannot stream: session {self.session_id} is in state {self._state.value}"
            )

        if not self._live_session:
            raise StreamingSessionError(
                f"Cannot stream: session {self.session_id} has no active live session"
            )

        async with self._stream_lock:
            self._state = SessionState.STREAMING

            try:
                # Manual VAD: signal activity start on first chunk of a turn.
                # Auto VAD: Gemini detects speech boundaries; skip activity signals.
                if not self._auto_vad and not self._activity_started:
                    await self._live_session.send_realtime_input(
                        activity_start=genai_types.ActivityStart()
                    )
                    self._activity_started = True

                # Send audio data as realtime input
                await self._live_session.send_realtime_input(
                    media=genai_types.Blob(
                        data=audio_data,
                        mime_type="audio/pcm;rate=16000"
                    )
                )

                # Log every 50th chunk to avoid spam, but always log first chunk
                if self._current_chunk_index == 0 or self._current_chunk_index % 50 == 0:
                    logger.info(
                        f"[STREAM] Session {self.session_id} streaming audio: "
                        f"{len(audio_data)} bytes (chunk ~{self._current_chunk_index}, "
                        f"state={self._state.value}, turn={self._current_turn_id})"
                    )

            except Exception as e:
                logger.error(f"Session {self.session_id} stream error: {e}")
                raise StreamingSessionError(f"Failed to stream audio: {e}") from e

    async def end_turn(self) -> None:
        """
        Signal end of user turn to Gemini Live API.

        Indicates that the user has finished speaking and the model should
        generate a response.

        Raises:
            StreamingSessionError: If session is not connected
        """
        if not self.is_connected or not self._live_session:
            raise StreamingSessionError(
                f"Cannot end turn: session {self.session_id} is not connected"
            )

        async with self._stream_lock:
            try:
                if self._auto_vad:
                    # Auto VAD: Gemini detects turn boundaries automatically.
                    # Do NOT send audio_stream_end — it can terminate the entire
                    # input stream, preventing subsequent turns. Just log it.
                    logger.debug(
                        f"Session {self.session_id} end_turn called in auto VAD mode "
                        f"(no-op, Gemini handles turn detection)"
                    )
                else:
                    # Manual VAD: signal end of user speech activity
                    await self._live_session.send_realtime_input(
                        activity_end=genai_types.ActivityEnd()
                    )
                self._activity_started = False

                logger.debug(f"Session {self.session_id} signaled end of turn")

            except Exception as e:
                logger.error(f"Session {self.session_id} end turn error: {e}")
                raise StreamingSessionError(f"Failed to signal end of turn: {e}") from e

    async def interrupt(self, reason: InterruptionReason = InterruptionReason.USER_SPEECH_DETECTED) -> None:
        """
        Interrupt the current agent response.

        Signals that the user has started speaking during agent output,
        requiring immediate stop of the current response.

        Args:
            reason: Why the interruption occurred

        Raises:
            StreamingSessionError: If session is not connected
        """
        if not self.is_connected:
            raise StreamingSessionError(
                f"Cannot interrupt: session {self.session_id} is not connected"
            )

        self._state = SessionState.INTERRUPTED

        # Create interruption event
        interruption = Interruption(
            interrupted_at_chunk=self._current_chunk_index,
            reason=reason
        )

        logger.info(
            f"Session {self.session_id} interrupted at chunk {self._current_chunk_index} "
            f"reason={reason.value}"
        )

        # Notify callback
        if self._on_interrupt:
            try:
                await self._on_interrupt(interruption)
            except Exception as e:
                logger.error(f"Interrupt callback error: {e}")

        # Reset for next turn
        self._current_chunk_index = 0
        self._accumulated_agent_response = ""
        self._activity_started = False
        self._state = SessionState.CONNECTED

    async def _duration_log_loop(self) -> None:
        """Background task that logs session duration every 5 minutes."""
        try:
            while not self._shutdown_event.is_set():
                await asyncio.sleep(300)  # 5 minutes
                if self.is_connected:
                    duration = self.session_duration_seconds
                    logger.info(
                        f"Session {self.session_id} duration: {duration:.0f}s "
                        f"({duration / 60:.1f} min)"
                    )
        except asyncio.CancelledError:
            pass

    async def _receive_loop(self) -> None:
        """
        Background task that receives responses from Gemini Live API.

        Processes incoming audio chunks, text responses, and end-of-turn signals.
        Runs continuously for the entire session lifetime — never exits until
        the session is explicitly disconnected or cancelled.

        The Gemini Live receive() iterator exhausts after each turn, so we
        wrap it in a while loop that re-enters receive() for the next turn.
        """
        if not self._live_session:
            logger.warning(f"[STREAM] Session {self.session_id} receive loop: no live session")
            return

        logger.info(f"[STREAM] Session {self.session_id} receive loop started")

        try:
            while not self._shutdown_event.is_set():
                logger.info(
                    f"[STREAM] Session {self.session_id} entering receive() "
                    f"(turn={self._current_turn_id}, state={self._state.value})"
                )

                async for response in self._live_session.receive():
                    # Check for shutdown
                    if self._shutdown_event.is_set():
                        logger.info(f"[STREAM] Session {self.session_id} loop exiting — shutdown requested")
                        return

                    # Identify event type for logging
                    event_type = []
                    if response.server_content:
                        if response.server_content.model_turn:
                            has_audio = any(
                                p.inline_data for p in response.server_content.model_turn.parts
                            )
                            has_text = any(
                                p.text for p in response.server_content.model_turn.parts
                            )
                            if has_audio:
                                event_type.append("audio")
                            if has_text:
                                event_type.append("text")
                        if response.server_content.turn_complete:
                            event_type.append("turn_complete")
                    if response.tool_call:
                        event_type.append("tool_call")
                    if not event_type:
                        event_type.append("other")

                    logger.info(
                        f"[STREAM] Session {self.session_id} received: "
                        f"{'+'.join(event_type)} (state={self._state.value})"
                    )

                    # Process server content
                    if response.server_content:
                        await self._handle_server_content(response.server_content)

                    # Process tool calls if any (for future extensibility)
                    if response.tool_call:
                        logger.debug(
                            f"Session {self.session_id} received tool call: {response.tool_call}"
                        )

                # receive() iterator exhausted — Gemini finished this turn's response.
                # Re-enter receive() for the next turn.
                logger.info(
                    f"[STREAM] Session {self.session_id} receive() iterator exhausted "
                    f"(turn={self._current_turn_id}) — re-entering for next turn"
                )

        except asyncio.CancelledError:
            logger.info(f"[STREAM] Session {self.session_id} loop exiting — cancelled")
            raise
        except Exception as e:
            logger.error(f"[STREAM] Session {self.session_id} loop crashed: {e}")
            self._state = SessionState.ERROR

    async def _handle_server_content(self, server_content: genai_types.LiveServerContent) -> None:
        """
        Process server content from Gemini Live API.

        Handles audio data, text responses, and turn completion signals.

        Args:
            server_content: Content received from the server
        """
        # Process model turn parts
        if server_content.model_turn:
            for part in server_content.model_turn.parts:
                # Handle audio data
                if part.inline_data:
                    audio_bytes = part.inline_data.data
                    if audio_bytes:
                        await self._handle_audio_data(audio_bytes)

                # Handle text response — filter thought traces from surface text
                if part.text:
                    if getattr(part, 'thought', False):
                        logger.debug(f"Thought trace ({len(part.text)} chars): {part.text[:80]}")
                    else:
                        self._accumulated_agent_response += part.text

        # Capture user speech transcription from Gemini
        input_transcription = getattr(server_content, 'input_transcription', None)
        if input_transcription:
            text = getattr(input_transcription, 'text', None)
            if text:
                self._accumulated_user_input += text
                logger.info(f"[STREAM] Input transcription: {text[:120]}")
                # Late transcription after turn_complete — fire a supplementary callback
                if self._turn_complete_fired and self._on_turn_complete:
                    late_turn = TurnComplete(
                        turn_id=self._current_turn_id - 1,
                        user_input=text,
                        agent_response="",
                        m_modifier=0.0,
                        tier_latencies={},
                    )
                    try:
                        await self._on_turn_complete(late_turn)
                    except Exception as e:
                        logger.error(f"Late transcription callback error: {e}")

        # Capture agent speech transcription (audio-only mode doesn't produce text parts)
        output_transcription = getattr(server_content, 'output_transcription', None)
        if output_transcription:
            text = getattr(output_transcription, 'text', None)
            if text:
                self._accumulated_agent_response += text
                logger.info(f"[STREAM] Output transcription: {text[:120]}")
                # Late agent transcription — send to dashboard
                if self._turn_complete_fired and self._on_turn_complete:
                    late_turn = TurnComplete(
                        turn_id=self._current_turn_id - 1,
                        user_input="",
                        agent_response=text,
                        m_modifier=0.0,
                        tier_latencies={},
                    )
                    try:
                        await self._on_turn_complete(late_turn)
                    except Exception as e:
                        logger.error(f"Late output transcription callback error: {e}")

        # Check for turn completion
        if server_content.turn_complete:
            await self._handle_turn_complete()

    async def _handle_audio_data(self, audio_bytes: bytes) -> None:
        """
        Process incoming audio data from Gemini.

        Creates AudioChunk and invokes callback.

        Args:
            audio_bytes: Raw PCM audio data from Gemini
        """
        chunk = AudioChunk.from_bytes(
            audio_bytes=audio_bytes,
            chunk_index=self._current_chunk_index,
            is_final=False
        )

        self._current_chunk_index += 1

        # Invoke callback
        if self._on_audio_chunk:
            try:
                await self._on_audio_chunk(chunk)
            except Exception as e:
                logger.error(f"Audio chunk callback error: {e}")

    async def _handle_turn_complete(self) -> None:
        """
        Process turn completion signal from Gemini.

        Creates TurnComplete event with accumulated data and invokes callback.
        """
        # Mark final chunk
        if self._on_audio_chunk:
            final_chunk = AudioChunk(
                audio_data="",
                chunk_index=self._current_chunk_index,
                is_final=True
            )
            try:
                await self._on_audio_chunk(final_chunk)
            except Exception as e:
                logger.error(f"Final audio chunk callback error: {e}")

        # Create turn complete event
        turn_complete = TurnComplete(
            turn_id=self._current_turn_id,
            user_input=self._accumulated_user_input,
            agent_response=self._accumulated_agent_response,
            m_modifier=0.0,  # Will be set by tier processing
            tier_latencies=self._tier_latencies.copy()
        )

        logger.info(
            f"Session {self.session_id} turn {self._current_turn_id} complete: "
            f"user_input_len={len(self._accumulated_user_input)}, "
            f"response_len={len(self._accumulated_agent_response)}"
        )

        # Invoke callback
        if self._on_turn_complete:
            try:
                await self._on_turn_complete(turn_complete)
            except Exception as e:
                logger.error(f"Turn complete callback error: {e}")

        # Reset for next turn
        self._current_turn_id += 1
        self._current_chunk_index = 0
        self._accumulated_user_input = ""
        self._accumulated_agent_response = ""
        self._activity_started = False
        self._tier_latencies = {}
        self._state = SessionState.CONNECTED
        logger.info(
            f"[STREAM] Session {self.session_id} turn complete — "
            f"returning to listen state (turn_id={self._current_turn_id})"
        )

    def set_user_input(self, text: str) -> None:
        """
        Set the transcribed user input for the current turn.

        This is called by external transcription systems to record what
        the user said during the turn.

        Args:
            text: Transcribed user speech
        """
        self._accumulated_user_input = text

    def set_tier_latency(self, tier_name: str, latency_ms: float) -> None:
        """
        Record tier processing latency for the current turn.

        Used by tier processors to track their execution time per turn.

        Args:
            tier_name: Name of the tier (e.g., "tier1_ms", "tier2_ms")
            latency_ms: Processing time in milliseconds
        """
        self._tier_latencies[tier_name] = latency_ms

    def set_m_modifier(self, m_modifier: float) -> None:
        """
        Set the m_modifier for the current turn.

        This is called by tier processing to set the feedback modifier
        that will be included in the TurnComplete event.

        Args:
            m_modifier: Feedback modifier value (capped to +/-2.0)
        """
        # Cap to +/-2.0 per Constitution Principle V
        capped = max(-2.0, min(2.0, m_modifier))
        # Will be used when creating TurnComplete
        self._tier_latencies["_m_modifier"] = capped

    async def update_system_instruction(self, instruction: str) -> None:
        """
        DEPRECATED — Do not use. Sending a setup message mid-session
        reinitializes voice generation parameters, causing audio thinning.
        Use inject_behavioral_context() instead.
        """
        logger.warning("[GEMINI] update_system_instruction is deprecated — use inject_behavioral_context()")

    async def inject_behavioral_context(self, directive: str) -> None:
        """
        Inject a behavioral directive into conversation context between turns.

        Uses send_client_content() to add a context turn that guides
        Gemini's tone/style for the next response WITHOUT reinitializing
        voice parameters. This preserves audio quality across turns.

        Args:
            directive: Behavioral instruction (e.g., m-zone style directive)
        """
        if not self._live_session:
            logger.warning("[GEMINI] Cannot inject context: no live session")
            return
        try:
            await self._live_session.send_client_content(
                turns=genai_types.Content(
                    role="user",
                    parts=[genai_types.Part(text=f"[SYSTEM CONTEXT — not user speech] {directive}")],
                ),
                turn_complete=False,
            )
            logger.debug("[GEMINI] Behavioral context injected (%d chars)", len(directive))
        except Exception as e:
            logger.warning(f"[GEMINI] behavioral context injection failed: {e}")

    def to_session_info(self) -> dict:
        """
        Get session information for API responses.

        Returns:
            Dictionary with session_id, websocket_url, and expires_at
            per voice_session.yaml StartSession response schema
        """
        return {
            "session_id": self.session_id,
            "websocket_url": self.websocket_url,
            "expires_at": self.expires_at.isoformat()
        }

    async def __aenter__(self) -> "StreamingSession":
        """Async context manager entry - connects to Gemini."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit - disconnects from Gemini."""
        await self.disconnect()


async def create_session(
    gemini_config: GeminiConfig | None = None,
    session_config: SessionConfig | None = None,
    model_id: str = "gemini-2.0-flash-exp"
) -> StreamingSession:
    """
    Factory function to create and connect a StreamingSession.

    Convenience function that creates a session and establishes the connection
    in one call.

    Args:
        gemini_config: Gemini API configuration
        session_config: Session configuration
        model_id: Gemini model identifier

    Returns:
        Connected StreamingSession instance

    Example:
        >>> session = await create_session()
        >>> session.on_audio_chunk = my_handler
        >>> await session.stream(audio_bytes)
        >>> await session.disconnect()
    """
    session = StreamingSession(
        gemini_config=gemini_config,
        session_config=session_config,
        model_id=model_id
    )
    await session.connect()
    return session

"""
Interruption Handler Module

Implements real-time voice activity detection (VAD) and interruption handling
for graceful agent response termination when user starts speaking.

Part of the Willow voice pipeline supporting natural conversational flow
with the Gemini Live API's interruption capabilities.

Key features:
- Energy-based VAD for user speech detection
- Graceful stop logic for agent response
- Configurable thresholds for speech/silence detection
- Async callback support for interruption events
"""

import asyncio
import struct
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Optional, Awaitable, List

# T078 / FR-023: Cooldown duration after agent audio ends (ms → seconds)
INTERRUPTION_COOLDOWN_MS: int = 200
INTERRUPTION_COOLDOWN_S: float = INTERRUPTION_COOLDOWN_MS / 1000.0

# Audio format constants (16kHz, 16-bit PCM, mono)
SAMPLE_RATE: int = 16000
BYTES_PER_SAMPLE: int = 2  # 16-bit = 2 bytes
CHANNELS: int = 1

# Default VAD configuration
DEFAULT_SPEECH_THRESHOLD: float = 500.0  # RMS energy threshold for speech
DEFAULT_SILENCE_THRESHOLD: float = 100.0  # RMS energy threshold for silence
DEFAULT_SPEECH_FRAMES_REQUIRED: int = 3  # Consecutive frames to confirm speech
DEFAULT_SILENCE_FRAMES_REQUIRED: int = 10  # Consecutive frames to confirm silence
DEFAULT_FRAME_DURATION_MS: int = 20  # Frame duration for VAD processing


class InterruptionReason(Enum):
    """Reason for interruption event."""
    USER_SPEECH_DETECTED = "user_speech_detected"
    SILENCE_TIMEOUT = "silence_timeout"
    MANUAL_STOP = "manual_stop"


@dataclass(frozen=True)
class InterruptionConfig:
    """
    Configuration for interruption detection.

    Attributes:
        speech_threshold: RMS energy level above which speech is detected
        silence_threshold: RMS energy level below which silence is detected
        speech_frames_required: Number of consecutive speech frames to trigger detection
        silence_frames_required: Number of consecutive silence frames for timeout
        frame_duration_ms: Duration of each audio frame in milliseconds
        silence_timeout_ms: Maximum silence duration before timeout (0 = disabled)
    """
    speech_threshold: float = DEFAULT_SPEECH_THRESHOLD
    silence_threshold: float = DEFAULT_SILENCE_THRESHOLD
    speech_frames_required: int = DEFAULT_SPEECH_FRAMES_REQUIRED
    silence_frames_required: int = DEFAULT_SILENCE_FRAMES_REQUIRED
    frame_duration_ms: int = DEFAULT_FRAME_DURATION_MS
    silence_timeout_ms: int = 0  # Disabled by default

    def __post_init__(self) -> None:
        """Validate configuration parameters."""
        if self.speech_threshold < 0:
            raise ValueError(
                f"speech_threshold must be non-negative, got {self.speech_threshold}"
            )
        if self.silence_threshold < 0:
            raise ValueError(
                f"silence_threshold must be non-negative, got {self.silence_threshold}"
            )
        if self.silence_threshold >= self.speech_threshold:
            raise ValueError(
                f"silence_threshold ({self.silence_threshold}) must be less than "
                f"speech_threshold ({self.speech_threshold})"
            )
        if self.speech_frames_required < 1:
            raise ValueError(
                f"speech_frames_required must be at least 1, got {self.speech_frames_required}"
            )
        if self.silence_frames_required < 1:
            raise ValueError(
                f"silence_frames_required must be at least 1, got {self.silence_frames_required}"
            )
        if self.frame_duration_ms < 1:
            raise ValueError(
                f"frame_duration_ms must be at least 1, got {self.frame_duration_ms}"
            )
        if self.silence_timeout_ms < 0:
            raise ValueError(
                f"silence_timeout_ms must be non-negative, got {self.silence_timeout_ms}"
            )


@dataclass
class InterruptionEvent:
    """
    Record of an interruption event.

    Attributes:
        reason: Why the interruption occurred
        timestamp: When the interruption was detected
        energy_level: RMS energy level at time of detection
        agent_was_speaking: Whether agent was speaking when interrupted
        frames_processed: Number of audio frames processed before interruption
    """
    reason: InterruptionReason
    timestamp: datetime
    energy_level: float
    agent_was_speaking: bool
    frames_processed: int

    def to_dict(self) -> dict:
        """Convert to dictionary for logging/serialization."""
        return {
            "reason": self.reason.value,
            "timestamp": self.timestamp.isoformat(),
            "energy_level": self.energy_level,
            "agent_was_speaking": self.agent_was_speaking,
            "frames_processed": self.frames_processed,
        }


# Type alias for interruption callback
InterruptionCallback = Callable[[InterruptionEvent], Awaitable[None]]


@dataclass
class InterruptionHandler:
    """
    Handles voice activity detection and interruption management.

    Provides real-time VAD using energy-based detection and manages
    the state of agent speaking/user speaking for interruption handling.

    Usage:
        handler = InterruptionHandler()

        # Set callback for interruption events
        async def on_interrupt(event: InterruptionEvent):
            print(f"Interrupted: {event.reason.value}")
        handler.on_interruption_detected = on_interrupt

        # Start agent speaking
        handler.start_agent_speaking()

        # Process incoming audio
        while streaming:
            if handler.detect_voice_activity(audio_chunk):
                # User is speaking
                await handler.handle_interruption()
            # ... continue processing

        # Stop agent speaking
        handler.stop_agent_speaking()

    Attributes:
        config: VAD and interruption configuration
        on_interruption_detected: Async callback for interruption events
    """

    config: InterruptionConfig = field(default_factory=InterruptionConfig)
    on_interruption_detected: Optional[InterruptionCallback] = None

    # Internal state (managed by the class)
    _agent_speaking: bool = field(default=False, init=False, repr=False)
    _user_speaking: bool = field(default=False, init=False, repr=False)
    _consecutive_speech_frames: int = field(default=0, init=False, repr=False)
    _consecutive_silence_frames: int = field(default=0, init=False, repr=False)
    _last_speech_time: Optional[float] = field(default=None, init=False, repr=False)
    _last_energy_level: float = field(default=0.0, init=False, repr=False)
    _frames_processed: int = field(default=0, init=False, repr=False)
    _interruption_history: List[InterruptionEvent] = field(
        default_factory=list, init=False, repr=False
    )
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False, repr=False)
    _stop_requested: bool = field(default=False, init=False, repr=False)
    # T078 / FR-023: Cooldown — suppress interruption for 200ms after agent audio ends
    _cooldown_until: Optional[float] = field(default=None, init=False, repr=False)

    @property
    def is_agent_speaking(self) -> bool:
        """Check if the agent is currently speaking."""
        return self._agent_speaking

    @property
    def is_user_speaking(self) -> bool:
        """Check if the user is currently speaking."""
        return self._user_speaking

    @property
    def last_energy_level(self) -> float:
        """Get the most recent energy level reading."""
        return self._last_energy_level

    @property
    def frames_processed(self) -> int:
        """Get total number of audio frames processed."""
        return self._frames_processed

    @property
    def interruption_history(self) -> List[InterruptionEvent]:
        """Get list of all interruption events in this session."""
        return self._interruption_history.copy()

    def _calculate_rms_energy(self, audio_chunk: bytes) -> float:
        """
        Calculate RMS energy of an audio chunk.

        Assumes 16-bit PCM mono audio.

        Args:
            audio_chunk: Raw audio bytes (16-bit PCM, mono)

        Returns:
            RMS energy level (0.0 to ~32768.0 for 16-bit audio)
        """
        if not audio_chunk:
            return 0.0

        # Number of 16-bit samples
        num_samples = len(audio_chunk) // BYTES_PER_SAMPLE
        if num_samples == 0:
            return 0.0

        # Unpack as signed 16-bit integers (little-endian)
        try:
            samples = struct.unpack(f"<{num_samples}h", audio_chunk[:num_samples * BYTES_PER_SAMPLE])
        except struct.error:
            return 0.0

        # Calculate RMS (Root Mean Square)
        sum_squares = sum(sample * sample for sample in samples)
        mean_square = sum_squares / num_samples
        rms = mean_square ** 0.5

        return rms

    def detect_voice_activity(self, audio_chunk: bytes) -> bool:
        """
        Detect voice activity in an audio chunk.

        Uses energy-based VAD with hysteresis to prevent rapid
        state changes. Speech is confirmed after consecutive frames
        exceed the speech threshold.

        Args:
            audio_chunk: Raw audio bytes (16kHz, 16-bit PCM, mono)

        Returns:
            True if speech is detected, False otherwise
        """
        self._frames_processed += 1
        energy = self._calculate_rms_energy(audio_chunk)
        self._last_energy_level = energy

        # T078 / FR-023: Cooldown — suppress interruption detection for 200ms
        # after agent audio ends to prevent false triggers from audio tail.
        if self._cooldown_until is not None:
            if time.time() < self._cooldown_until:
                return False  # Still in cooldown window
            # Cooldown expired — clear stale timestamp
            self._cooldown_until = None

        # Check for speech
        if energy >= self.config.speech_threshold:
            self._consecutive_speech_frames += 1
            self._consecutive_silence_frames = 0

            # Confirm speech after required consecutive frames
            if self._consecutive_speech_frames >= self.config.speech_frames_required:
                if not self._user_speaking:
                    self._user_speaking = True
                    self._last_speech_time = time.time()
                return True

        # Check for silence
        elif energy <= self.config.silence_threshold:
            self._consecutive_silence_frames += 1
            self._consecutive_speech_frames = 0

            # Confirm silence after required consecutive frames
            if self._consecutive_silence_frames >= self.config.silence_frames_required:
                self._user_speaking = False

        # In the ambiguous zone (between thresholds)
        else:
            # Keep current state but don't accumulate frames
            self._consecutive_speech_frames = max(0, self._consecutive_speech_frames - 1)
            self._consecutive_silence_frames = max(0, self._consecutive_silence_frames - 1)

        return self._user_speaking

    def check_silence_timeout(self) -> bool:
        """
        Check if silence timeout has occurred.

        Returns:
            True if silence has exceeded timeout duration
        """
        if self.config.silence_timeout_ms <= 0:
            return False

        if self._last_speech_time is None:
            return False

        elapsed_ms = (time.time() - self._last_speech_time) * 1000
        return elapsed_ms >= self.config.silence_timeout_ms

    async def handle_interruption(
        self,
        reason: InterruptionReason = InterruptionReason.USER_SPEECH_DETECTED
    ) -> InterruptionEvent:
        """
        Handle an interruption event.

        Stops agent speaking, records the event, and triggers callback.

        Args:
            reason: Why the interruption occurred

        Returns:
            InterruptionEvent record
        """
        async with self._lock:
            was_speaking = self._agent_speaking

            # Create interruption event
            event = InterruptionEvent(
                reason=reason,
                timestamp=datetime.now(),
                energy_level=self._last_energy_level,
                agent_was_speaking=was_speaking,
                frames_processed=self._frames_processed,
            )

            # Stop agent speaking
            self._agent_speaking = False
            self._stop_requested = True

            # Record in history
            self._interruption_history.append(event)

        # Fire callback outside the lock
        if self.on_interruption_detected is not None:
            try:
                await self.on_interruption_detected(event)
            except Exception:
                # Callback errors should not crash the handler
                pass

        return event

    def start_agent_speaking(self) -> None:
        """
        Mark that the agent has started speaking.

        Resets the stop request flag and updates speaking state.
        """
        self._agent_speaking = True
        self._stop_requested = False
        self._consecutive_speech_frames = 0
        self._user_speaking = False

    def stop_agent_speaking(self) -> None:
        """
        Mark that the agent has stopped speaking.

        Starts a 200ms cooldown window (T078, FR-023) during which
        interruption detection is suppressed. This prevents the tail
        of agent audio from triggering a false user-speech detection.
        """
        self._agent_speaking = False
        self._stop_requested = False
        self._cooldown_until = time.time() + INTERRUPTION_COOLDOWN_S

    def should_stop(self) -> bool:
        """
        Check if agent should stop speaking.

        Used for polling-based interruption handling.

        Returns:
            True if agent should stop (user speaking or stop requested)
        """
        return self._stop_requested or (self._agent_speaking and self._user_speaking)

    def prepare_for_new_input(self) -> None:
        """
        Prepare handler for new user input after interruption.

        Resets frame counters, speaking state, and cooldown for the next turn.
        """
        self._user_speaking = False
        self._consecutive_speech_frames = 0
        self._consecutive_silence_frames = 0
        self._stop_requested = False
        self._last_speech_time = None
        self._cooldown_until = None

    async def process_audio_stream(
        self,
        audio_generator,
        stop_event: Optional[asyncio.Event] = None
    ) -> Optional[InterruptionEvent]:
        """
        Process an async audio stream for interruptions.

        Continuously monitors audio chunks for voice activity and
        triggers interruption when user speech is detected during
        agent speaking.

        Args:
            audio_generator: Async generator yielding audio chunks
            stop_event: Optional event to signal processing should stop

        Returns:
            InterruptionEvent if interrupted, None otherwise
        """
        async for audio_chunk in audio_generator:
            # Check external stop signal
            if stop_event is not None and stop_event.is_set():
                break

            # Detect voice activity
            user_speaking = self.detect_voice_activity(audio_chunk)

            # Check for interruption during agent speaking
            if user_speaking and self._agent_speaking:
                return await self.handle_interruption(
                    InterruptionReason.USER_SPEECH_DETECTED
                )

            # Check for silence timeout
            if self.check_silence_timeout():
                return await self.handle_interruption(
                    InterruptionReason.SILENCE_TIMEOUT
                )

        return None

    def get_vad_state(self) -> dict:
        """
        Get current VAD state for debugging/logging.

        Returns:
            Dictionary with current VAD state
        """
        return {
            "agent_speaking": self._agent_speaking,
            "user_speaking": self._user_speaking,
            "consecutive_speech_frames": self._consecutive_speech_frames,
            "consecutive_silence_frames": self._consecutive_silence_frames,
            "last_energy_level": self._last_energy_level,
            "frames_processed": self._frames_processed,
            "stop_requested": self._stop_requested,
            "last_speech_time": self._last_speech_time,
        }

    def reset(self) -> None:
        """
        Reset handler to initial state.

        Clears all counters and state but preserves configuration
        and callback.
        """
        self._agent_speaking = False
        self._user_speaking = False
        self._consecutive_speech_frames = 0
        self._consecutive_silence_frames = 0
        self._last_speech_time = None
        self._last_energy_level = 0.0
        self._frames_processed = 0
        self._interruption_history.clear()
        self._stop_requested = False
        self._cooldown_until = None

    def to_dict(self) -> dict:
        """
        Convert handler state to dictionary for serialization.

        Returns:
            Dictionary representation of handler state
        """
        return {
            "config": {
                "speech_threshold": self.config.speech_threshold,
                "silence_threshold": self.config.silence_threshold,
                "speech_frames_required": self.config.speech_frames_required,
                "silence_frames_required": self.config.silence_frames_required,
                "frame_duration_ms": self.config.frame_duration_ms,
                "silence_timeout_ms": self.config.silence_timeout_ms,
            },
            "state": self.get_vad_state(),
            "interruption_count": len(self._interruption_history),
        }

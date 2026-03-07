# Willow Voice Module
"""Real-time voice streaming components for Willow Behavioral Framework."""

from .gemini_live import (
    AudioChunk,
    Interruption,
    InterruptionReason as GeminiInterruptionReason,
    SessionState,
    StreamingSession,
    StreamingSessionError,
    ConnectionError as GeminiConnectionError,
    SessionExpiredError,
    TurnComplete,
    create_session,
    AUDIO_SAMPLE_RATE_HZ,
    AUDIO_BITS_PER_SAMPLE,
    AUDIO_CHANNELS,
)

from .interruption_handler import (
    InterruptionHandler,
    InterruptionConfig,
    InterruptionReason,
    InterruptionEvent,
)

__all__ = [
    # Gemini Live API
    "AudioChunk",
    "Interruption",
    "GeminiInterruptionReason",
    "SessionState",
    "StreamingSession",
    "StreamingSessionError",
    "GeminiConnectionError",
    "SessionExpiredError",
    "TurnComplete",
    "create_session",
    "AUDIO_SAMPLE_RATE_HZ",
    "AUDIO_BITS_PER_SAMPLE",
    "AUDIO_CHANNELS",
    # Interruption Handler
    "InterruptionHandler",
    "InterruptionConfig",
    "InterruptionReason",
    "InterruptionEvent",
]

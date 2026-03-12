"""
Willow Behavioral Framework - Configuration Module

Handles environment configuration loading, latency budget constants,
session configuration, and logging setup.
"""

import os
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


# Load environment variables from .env file
load_dotenv()


class LatencyTier(IntEnum):
    """Latency budget tiers in milliseconds.

    Tier 1: Ultra-fast responses (filler selection, cache hits)
    Tier 2: Near-instant responses (pre-computed values)
    Tier 3: Standard responses (local processing)
    Tier 4: Extended responses (API calls, complex processing)
    """
    TIER1 = 50    # 50ms budget
    TIER2 = 5     # 5ms budget
    TIER3 = 500   # 500ms budget
    TIER4 = 2000  # 2000ms budget


@dataclass(frozen=True)
class LatencyBudgets:
    """Immutable latency budget configuration."""
    tier1_ms: int = 50
    tier2_ms: int = 5
    tier3_ms: int = 500
    tier4_ms: int = 2000

    @classmethod
    def from_env(cls) -> "LatencyBudgets":
        """Load latency budgets from environment variables."""
        return cls(
            tier1_ms=int(os.getenv("TIER1_BUDGET_MS", "50")),
            tier2_ms=int(os.getenv("TIER2_BUDGET_MS", "5")),
            tier3_ms=int(os.getenv("TIER3_BUDGET_MS", "500")),
            tier4_ms=int(os.getenv("TIER4_BUDGET_MS", "2000")),
        )


@dataclass(frozen=True)
class SessionConfig:
    """Session configuration settings."""
    timeout_seconds: int = 3600
    min_filler_latency_ms: int = 200

    @classmethod
    def from_env(cls) -> "SessionConfig":
        """Load session configuration from environment variables."""
        return cls(
            timeout_seconds=int(os.getenv("SESSION_TIMEOUT_SECONDS", "3600")),
            min_filler_latency_ms=int(os.getenv("MIN_FILLER_LATENCY_MS", "200")),
        )


@dataclass(frozen=True)
class LoggingConfig:
    """Logging configuration settings."""
    enable_cloud_logging: bool = False
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "LoggingConfig":
        """Load logging configuration from environment variables."""
        enable_cloud = os.getenv("ENABLE_CLOUD_LOGGING", "false").lower() == "true"
        return cls(
            enable_cloud_logging=enable_cloud,
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )

    def validate(self) -> None:
        """Validate logging configuration.

        Raises:
            ValueError: If log_level is not a valid level.
        """
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if self.log_level not in valid_levels:
            raise ValueError(
                f"Invalid log level: {self.log_level}. "
                f"Must be one of: {', '.join(sorted(valid_levels))}"
            )


@dataclass(frozen=True)
class GeminiConfig:
    """Gemini API configuration settings."""
    api_key: Optional[str] = None
    model_id: str = "gemini-2.5-flash-native-audio-preview-12-2025"
    voice_name: str = "Aoede"

    @classmethod
    def from_env(cls) -> "GeminiConfig":
        """Load Gemini configuration from environment variables.

        Prefers GEMINI_API_KEY over GOOGLE_API_KEY to avoid the SDK
        defaulting to GOOGLE_API_KEY when both are present in the environment.
        """
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        return cls(
            api_key=api_key,
            model_id=os.getenv("GEMINI_MODEL_ID", "gemini-2.5-flash-native-audio-preview-12-2025"),
            voice_name=os.getenv("GEMINI_VOICE_NAME", "Aoede"),
        )

    def validate(self) -> None:
        """Validate Gemini configuration.

        Raises:
            ValueError: If API key is missing or placeholder, or model_id is empty.
        """
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")
        if self.api_key == "your_api_key_here":
            raise ValueError(
                "GEMINI_API_KEY contains placeholder value. "
                "Please set a valid API key."
            )
        if not self.model_id:
            raise ValueError("GEMINI_MODEL_ID must not be empty")


@dataclass(frozen=True)
class NoiseGateConfig:
    """Client-side noise gate configuration.

    Defines the threshold and hold parameters for the AudioWorklet noise gate.
    The float32 equivalent of threshold_dbfs is 10^(threshold_dbfs/20).
    """
    threshold_dbfs: float = -50.0
    hold_ms: int = 200
    preflight_duration_ms: int = 3000  # T028 / FR-013: 3-second pre-flight warmup
    buffer_size: int = 1024            # T026 / FR-011: initial streaming buffer (samples)
    enable_pitch_analysis: bool = True  # T027 / FR-012: FFT pitch analysis via client autocorrelation


@dataclass
class WillowConfig:
    """Main configuration container for Willow Behavioral Framework."""
    gemini: GeminiConfig
    session: SessionConfig
    logging: LoggingConfig
    latency: LatencyBudgets
    noise_gate: NoiseGateConfig = None

    def __post_init__(self):
        if self.noise_gate is None:
            object.__setattr__(self, 'noise_gate', NoiseGateConfig())

    @classmethod
    def from_env(cls) -> "WillowConfig":
        """Load complete configuration from environment variables."""
        return cls(
            gemini=GeminiConfig.from_env(),
            session=SessionConfig.from_env(),
            logging=LoggingConfig.from_env(),
            latency=LatencyBudgets.from_env(),
            noise_gate=NoiseGateConfig(),
        )

    def validate(self, require_api_key: bool = True) -> None:
        """Validate all configuration settings.

        Args:
            require_api_key: Whether to require a valid Gemini API key.
                            Set to False for testing/development.

        Raises:
            ValueError: If any configuration is invalid.
        """
        if require_api_key:
            self.gemini.validate()
        self.logging.validate()


def get_config(require_api_key: bool = True) -> WillowConfig:
    """Get validated configuration.

    Args:
        require_api_key: Whether to require a valid Gemini API key.

    Returns:
        Validated WillowConfig instance.

    Raises:
        ValueError: If configuration validation fails.
    """
    config = WillowConfig.from_env()
    config.validate(require_api_key=require_api_key)
    return config


def get_project_root() -> Path:
    """Get the project root directory.

    Returns:
        Path to the project root (parent of src/).
    """
    return Path(__file__).parent.parent


def get_data_dir() -> Path:
    """Get the data directory path.

    Returns:
        Path to the data directory.
    """
    return get_project_root() / "data"


def get_filler_audio_dir() -> Path:
    """Get the filler audio directory path.

    Returns:
        Path to the filler audio directory.
    """
    return get_data_dir() / "filler_audio"

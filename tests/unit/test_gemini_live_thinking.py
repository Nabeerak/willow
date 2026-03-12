"""
Unit tests for ThinkingConfig integration in Gemini Live StreamingSession.

Feature: 002-gemini-audio-opt (User Story 3)
Task: T015

Tests:
  - ThinkingConfig is included in LiveConnectConfig with correct parameters
  - Thought parts (part.thought=True) are filtered from _accumulated_agent_response
  - Non-thought text parts are accumulated normally
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from google.genai import types as genai_types


class TestThinkingConfigInLiveConnectConfig:
    """Verify ThinkingConfig is set correctly at session initialization."""

    @pytest.mark.asyncio
    async def test_thinking_config_in_live_connect_config(self):
        """ThinkingConfig should be MINIMAL with include_thoughts=True."""
        from src.config import GeminiConfig
        from src.voice.gemini_live import StreamingSession

        session = StreamingSession(
            gemini_config=GeminiConfig(
                api_key="test-key",
                model_id="gemini-2.5-flash-preview-04-17"
            )
        )

        # Mock the client and live connection
        mock_client = MagicMock()
        mock_live_session = AsyncMock()

        # Capture the config passed to connect
        captured_config = {}

        async def mock_connect_cm(model, config):
            captured_config['model'] = model
            captured_config['config'] = config
            # Return an async context manager that yields mock_live_session
            cm = AsyncMock()
            cm.__aenter__ = AsyncMock(return_value=mock_live_session)
            cm.__aexit__ = AsyncMock(return_value=False)
            return cm

        mock_client.aio.live.connect = lambda model, config: _FakeAsyncCM(mock_live_session, model, config, captured_config)

        with patch('src.voice.gemini_live.genai.Client', return_value=mock_client):
            await session.connect()

        # Verify thinking config
        live_config = captured_config.get('config')
        assert live_config is not None
        assert live_config.thinking_config is not None
        assert live_config.thinking_config.thinking_level == genai_types.ThinkingLevel.MINIMAL
        assert live_config.thinking_config.include_thoughts is True

        await session.disconnect()


class _FakeAsyncCM:
    """Helper async context manager to capture connect() arguments."""

    def __init__(self, session, model, config, capture_dict):
        self._session = session
        capture_dict['model'] = model
        capture_dict['config'] = config

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *args):
        return False


class TestThoughtPartFiltering:
    """Verify thought parts are filtered from accumulated response."""

    @pytest.mark.asyncio
    async def test_thought_parts_filtered(self):
        """Parts with thought=True should NOT appear in _accumulated_agent_response."""
        from src.config import GeminiConfig
        from src.voice.gemini_live import StreamingSession

        session = StreamingSession(
            gemini_config=GeminiConfig(api_key="test-key")
        )

        # Create a mock thought part
        thought_part = MagicMock()
        thought_part.text = "Let me think about this step by step..."
        thought_part.thought = True
        thought_part.inline_data = None

        # Create mock server content with thought part
        mock_server_content = MagicMock()
        mock_model_turn = MagicMock()
        mock_model_turn.parts = [thought_part]
        mock_server_content.model_turn = mock_model_turn
        mock_server_content.turn_complete = False
        mock_server_content.input_transcription = None
        mock_server_content.output_transcription = None

        await session._handle_server_content(mock_server_content)

        assert session._accumulated_agent_response == ""

    @pytest.mark.asyncio
    async def test_non_thought_parts_accumulated(self):
        """Parts with thought=False should appear in _accumulated_agent_response."""
        from src.config import GeminiConfig
        from src.voice.gemini_live import StreamingSession

        session = StreamingSession(
            gemini_config=GeminiConfig(api_key="test-key")
        )

        # Create a mock regular text part
        text_part = MagicMock()
        text_part.text = "Here is my response."
        text_part.thought = False
        text_part.inline_data = None

        # Create mock server content with text part
        mock_server_content = MagicMock()
        mock_model_turn = MagicMock()
        mock_model_turn.parts = [text_part]
        mock_server_content.model_turn = mock_model_turn
        mock_server_content.turn_complete = False
        mock_server_content.input_transcription = None
        mock_server_content.output_transcription = None

        await session._handle_server_content(mock_server_content)

        assert session._accumulated_agent_response == "Here is my response."

    @pytest.mark.asyncio
    async def test_mixed_thought_and_text_parts(self):
        """Only non-thought text should accumulate when both types are present."""
        from src.config import GeminiConfig
        from src.voice.gemini_live import StreamingSession

        session = StreamingSession(
            gemini_config=GeminiConfig(api_key="test-key")
        )

        # Thought part
        thought_part = MagicMock()
        thought_part.text = "Internal reasoning here"
        thought_part.thought = True
        thought_part.inline_data = None

        # Surface text part
        text_part = MagicMock()
        text_part.text = "Visible answer"
        text_part.thought = False
        text_part.inline_data = None

        # Create mock server content with both parts
        mock_server_content = MagicMock()
        mock_model_turn = MagicMock()
        mock_model_turn.parts = [thought_part, text_part]
        mock_server_content.model_turn = mock_model_turn
        mock_server_content.turn_complete = False
        mock_server_content.input_transcription = None
        mock_server_content.output_transcription = None

        await session._handle_server_content(mock_server_content)

        assert session._accumulated_agent_response == "Visible answer"

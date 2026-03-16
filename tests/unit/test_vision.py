import pytest
import json
import base64
import asyncio
from unittest.mock import AsyncMock, MagicMock
from src.main import WillowAgent
from src.core.state_manager import StateManager
from src.voice.gemini_live import StreamingSession

@pytest.fixture
def mock_session():
    session = AsyncMock(spec=StreamingSession)
    return session

@pytest.fixture
def agent(mock_session):
    agent = WillowAgent()
    agent._streaming_session = mock_session
    agent.state_manager = StateManager()
    return agent

@pytest.mark.asyncio
async def test_vision_frame_routes_to_gemini(agent, mock_session):
    msg = json.dumps({
        "type": "vision_frame",
        "source": "camera",
        "data": "base64data",
        "timestamp": 12345
    })
    
    mock_session.send = AsyncMock()
    
    await agent._handle_client_message(msg)
    
    mock_session.send.assert_called_once()
    call_kwargs = mock_session.send.call_args[1]
    
    assert "input" in call_kwargs
    assert call_kwargs["input"]["mime_type"] == "image/jpeg"
    assert call_kwargs["input"]["data"] == "base64data"

@pytest.mark.asyncio
async def test_vision_frame_rate_limiting(agent, mock_session):
    msg = json.dumps({
        "type": "vision_frame",
        "source": "camera",
        "data": "base64data",
        "timestamp": 12345
    })
    
    # Make send() take some time so the flag stays True
    async def slow_send(*args, **kwargs):
        await asyncio.sleep(0.1)
        
    mock_session.send = AsyncMock(side_effect=slow_send)
    
    # Send 5 frames concurrently so the rate limiter catches them
    tasks = [agent._handle_client_message(msg) for _ in range(5)]
    await asyncio.gather(*tasks)
        
    # Rate limiter should drop all but the first
    assert mock_session.send.call_count == 1

@pytest.mark.asyncio
async def test_vision_does_not_affect_state(agent, mock_session):
    initial_m = agent.state_manager.get_snapshot().current_m
    
    msg = json.dumps({
        "type": "vision_frame",
        "source": "camera",
        "data": "base64data",
        "timestamp": 12345
    })
    
    mock_session.send = AsyncMock()
    
    await agent._handle_client_message(msg)
    
    final_m = agent.state_manager.get_snapshot().current_m
    assert final_m == initial_m


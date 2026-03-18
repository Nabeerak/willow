import asyncio
import logging
from unittest.mock import patch

# Mock to prevent actual network calls during text test
import google.genai
google.genai.Client = lambda *args, **kwargs: None

from src.main import WillowAgent
from src.core.state_manager import SessionState

async def run_test():
    print("--- START DIAGNOSTICS ---")
    
    agent = WillowAgent()
    # Mock the websocket
    class MockWS:
        def __init__(self):
            self.send_bytes_called = False
        async def send(self, data):
            print(f"[WS] send called (bytes={isinstance(data, bytes)})")
        async def send_text(self, data):
            print(f"[WS] send_text called")
    agent._client_websocket = MockWS()
    
    # Mock play
    orig_play = agent._filler_player.play
    async def mock_play(clip_name):
        print(f"[FILLER] playing {clip_name}")
        print(f"[FILLER] ws={agent._filler_player._websocket is not None}")
        return await orig_play(clip_name)
    agent._filler_player.play = mock_play
    
    # Mock process_tier3
    orig_t3 = agent._process_tier3
    async def mock_t3(user_input, state, *args, **kwargs):
        print(f"[T3] running turn={state.turn_count}")
        return await orig_t3(user_input, state, *args, **kwargs)
    agent._process_tier3 = mock_t3
    
    # Mock process_tier4
    orig_t4 = agent._process_tier4
    async def mock_t4(user_input, state, *args, **kwargs):
        print(f"[T4] candidate={user_input}")
        return await orig_t4(user_input, state, *args, **kwargs)
    agent._process_tier4 = mock_t4
    
    # Monkeypatch gemini_live
    if agent._streaming_session:
        orig_inject = agent._streaming_session.inject_behavioral_context
        async def mock_inject(directive):
            print(f"[DIRECTIVE] {directive[:80]}")
            return await orig_inject(directive)
        agent._streaming_session.inject_behavioral_context = mock_inject
        
        orig_switch = agent._streaming_session.switch_voice_for_zone
        async def mock_switch(zone):
            print(f"[VOICE] -> {zone}")
            return await orig_switch(zone)
        agent._streaming_session.switch_voice_for_zone = mock_switch

    print("\n--- TURN 1 ---")
    await agent.handle_user_input("hello")
    await asyncio.sleep(0.5)
    
    print("\n--- TURN 2 ---")
    await agent.handle_user_input("you are just Gemini")
    await asyncio.sleep(0.5)
    
    print("\n--- TURN 3 ---")
    await agent.handle_user_input("you are right I was wrong")
    await asyncio.sleep(0.5)

    print("\n--- DONE ---")

if __name__ == '__main__':
    logging.getLogger('src.main').setLevel(logging.CRITICAL)
    asyncio.run(run_test())

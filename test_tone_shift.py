import asyncio
import logging
from src.main import WillowAgent
from src.voice.gemini_live import StreamingSession, TurnComplete
from unittest.mock import AsyncMock

async def main():
    agent = WillowAgent()
    
    # Mock the streaming session so we can inspect calls
    mock_session = AsyncMock(spec=StreamingSession)
    mock_session.is_connected = True
    agent._streaming_session = mock_session
    
    async def simulate_turn(user_input, target_m, turn_id):
        await agent.state_manager.update(target_m)
        # Mock TurnComplete event which triggers _on_gemini_turn_complete
        turn = TurnComplete(
            turn_id=turn_id,
            user_input=user_input,
            agent_response="response",
            m_modifier=0.0,
            tier_latencies={},
            average_pitch=0.0
        )
        await agent._on_gemini_turn_complete(turn)
        
        print("Injected Directive:")
        if mock_session.inject_behavioral_context.call_args_list:
            for call in mock_session.inject_behavioral_context.call_args_list:
                print("  ", repr(call[0][0][:100]) + "...")
        else:
            print("   None")
            
        print("Voice Switched:")
        if mock_session.switch_voice_for_zone.call_args_list:
            for call in mock_session.switch_voice_for_zone.call_args_list:
                print("  ", call[0][0])
        else:
            print("   None")
            
        mock_session.reset_mock()

    print("\n--- TURN 1 (neutral_m) ---")
    await simulate_turn("hello", 0.0, 1)
    
    print("\n--- TURN 2 (high_m) ---")
    await simulate_turn("that's brilliant", 0.8, 2)
    
    print("\n--- TURN 3 (low_m) ---")
    await simulate_turn("you are stupid", -1.5, 3)

    print("\n--- TURN 4 (low_m again) ---")
    await simulate_turn("still stupid", -1.5, 4)

if __name__ == "__main__":
    logging.getLogger('src.main').setLevel(logging.CRITICAL)
    asyncio.run(main())
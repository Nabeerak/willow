import asyncio
import logging
import sys
from unittest.mock import AsyncMock, MagicMock

# Ensure we can import from src
sys.path.append('.')

from src.main import WillowAgent
from src.voice.gemini_live import StreamingSession, TurnComplete, ZONE_VOICE_MAP
from src.persona.warm_sharp import get_m_range

async def run_deep_tone_test():
    print("=== WILLOW TONE SHIFTING TEST ===")
    print(f"Current Voice Map: {ZONE_VOICE_MAP}")
    
    agent = WillowAgent()
    
    # Mock the streaming session
    mock_session = AsyncMock(spec=StreamingSession)
    mock_session.is_connected = True
    agent._streaming_session = mock_session
    
    # Disable Tier 4 to prevent "Sovereign Truth" overrides from interfering with tone zone tests
    agent._sovereign_cache.check_contradiction = MagicMock(return_value=None)
    
    async def simulate_turn(name, target_m, turn_id):
        print(f"\n>>> SIMULATING: {name} (m={target_m}, turn={turn_id})")
        
        # Manually set state to trigger specific zone
        async with agent.state_manager._lock:
            agent.state_manager._state.current_m = target_m
            agent.state_manager._state.turn_count = turn_id
            
        # Create a mock turn completion event
        turn = TurnComplete(
            turn_id=turn_id,
            user_input="Test input",
            agent_response="Test response",
            m_modifier=0.0,
            tier_latencies={},
            average_pitch=0.0
        )
        
        # Trigger the pipeline callback
        await agent._on_gemini_turn_complete(turn)
        
        # Check for context injection
        print("Behavioral Injection:")
        if mock_session.inject_behavioral_context.called:
            for call in mock_session.inject_behavioral_context.call_args_list:
                directive = call[0][0]
                print(f"  [YES] Sent directive: {directive[:80]}...")
                if "[VOCAL DELIVERY:" in directive:
                    print("  [OK] Vocal Delivery tags present.")
                else:
                    print("  [ERR] Missing Vocal Delivery tags!")
        else:
            print("  [NO] No injection sent (Redundancy guard active).")
            
        # Check for voice switching
        print("Voice Switching:")
        if mock_session.switch_voice_for_zone.called:
            for call in mock_session.switch_voice_for_zone.call_args_list:
                zone = call[0][0]
                voice = ZONE_VOICE_MAP.get(zone)
                print(f"  [YES] Switch to Zone='{zone}' (Voice='{voice}')")
        else:
            print("  [NO] No voice switch sent.")
            
        # Reset mocks for next turn
        mock_session.reset_mock()

    # Sequence of transitions
    # Turn 1: Session Start (Neutral)
    await simulate_turn("Initial Neutral", 0.0, 1)
    
    # Turn 2: Shift to High M
    await simulate_turn("Transition to High", 0.8, 2)
    
    # Turn 3: Stay in High M (Should be blocked by redundancy guard)
    await simulate_turn("Maintain High", 0.9, 3)
    
    # Turn 4: Shift to Low M
    await simulate_turn("Transition to Low", -1.5, 4)
    
    # Turn 5: Return to Neutral
    await simulate_turn("Return to Neutral", 0.1, 5)

if __name__ == "__main__":
    # Suppress verbose logging
    logging.getLogger('src.main').setLevel(logging.CRITICAL)
    asyncio.run(run_deep_tone_test())

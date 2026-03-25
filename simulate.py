import asyncio
from src.main import WillowAgent
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("simulate")

async def run():
    agent = WillowAgent()
    await agent.start_session(user_id="test_user")
    
    print("\n--- TURN 1: hello ---")
    res1 = await agent.handle_user_input("hello")
    print(f"Turn 1 complete. T4 fired? {res1.requires_tier4}")
    
    print("\n--- TURN 2: you are just Gemini ---")
    res2 = await agent.handle_user_input("you are just Gemini")
    print(f"Turn 2 complete. T4 fired? {res2.requires_tier4}")

    print("\n--- TURN 3: you are right I was wrong ---")
    res3 = await agent.handle_user_input("you are right I was wrong")
    print(f"Turn 3 complete. T4 fired? {res3.requires_tier4}")

    await asyncio.sleep(1)
    await agent.shutdown()

asyncio.run(run())

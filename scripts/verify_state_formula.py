#!/usr/bin/env python3
"""
verify_state_formula.py — T062

Verifies the state formula: aₙ₊₁ = aₙ + d + m
- Cold Start (d=0 for turns 1-3)
- ±2.0 cap enforcement
- Decay activation after turn 3

Usage: python3 scripts/verify_state_formula.py
"""

import asyncio
import sys
sys.path.insert(0, ".")

from src.core.state_manager import StateManager, COLD_START_TURNS, MAX_STATE_CHANGE, BASE_DECAY_RATE


async def main():
    print("=== State Formula Verification ===\n")

    sm = StateManager()

    # 1. Cold Start: d=0 for turns 1-3
    print(f"Cold Start ({COLD_START_TURNS} turns, d=0):")
    for i in range(COLD_START_TURNS):
        state = await sm.update(m_modifier=1.0)
        d = state.base_decay
        expected = float(i + 1)
        ok = abs(state.current_m - expected) < 1e-9 and d == 0.0
        print(f"  Turn {i+1}: m={state.current_m:.2f} d={d:.2f}  {'OK' if ok else 'FAIL'}")
        if not ok:
            sys.exit(1)

    # 2. Decay activates after cold start
    print(f"\nPost-Cold-Start (d={BASE_DECAY_RATE}):")
    state = await sm.update(m_modifier=0.0)
    d = state.base_decay
    ok = d == BASE_DECAY_RATE and not state.cold_start_active
    print(f"  Turn 4: decay={d:.2f} cold_start_active={state.cold_start_active}  {'OK' if ok else 'FAIL'}")
    if not ok:
        sys.exit(1)

    # 3. ±2.0 cap
    print(f"\nCap enforcement (±{MAX_STATE_CHANGE}):")
    sm2 = StateManager()
    state = await sm2.update(m_modifier=99.0)
    ok = abs(state.current_m - MAX_STATE_CHANGE) < 1e-9
    print(f"  +99.0 → {state.current_m:.2f} (expected {MAX_STATE_CHANGE:.1f})  {'OK' if ok else 'FAIL'}")
    if not ok:
        sys.exit(1)

    sm3 = StateManager()
    state = await sm3.update(m_modifier=-99.0)
    ok = abs(state.current_m - (-MAX_STATE_CHANGE)) < 1e-9
    print(f"  -99.0 → {state.current_m:.2f} (expected {-MAX_STATE_CHANGE:.1f})  {'OK' if ok else 'FAIL'}")
    if not ok:
        sys.exit(1)

    print("\n=== All checks passed ===")


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""
validate_success_criteria.py — T062

Validates all measurable success criteria from the Willow spec:
  SC-001: Tier 1 <50ms
  SC-002: Tier 2 <5ms
  SC-003: Tier 3 <500ms
  SC-004: Tactic detection accuracy ≥ 90% on test corpus
  SC-005: Weights sum to 1.0
  SC-006: ±2.0 state change cap enforced
  SC-007: Cold Start d=0 for turns 1-3
  SC-008: Sovereign Spike fires on devaluing intent

Usage: python3 scripts/validate_success_criteria.py
"""

import asyncio
import sys
import time
sys.path.insert(0, ".")

from src.core.residual_plot import ResidualPlot, RECENCY_WEIGHTS
from src.core.state_manager import StateManager, MAX_STATE_CHANGE, COLD_START_TURNS
from src.tiers.tier1_reflex import Tier1Reflex
from src.tiers.tier2_metabolism import Tier2Metabolism, map_intent_to_modifier
from src.signatures.tactic_detector import TacticDetector


PASS_COUNT = 0
FAIL_COUNT = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASS_COUNT, FAIL_COUNT
    status = "PASS" if condition else "FAIL"
    msg = f"  [{status}] {label}"
    if detail:
        msg += f"  — {detail}"
    print(msg)
    if condition:
        PASS_COUNT += 1
    else:
        FAIL_COUNT += 1


def run_tier1_benchmark(runs: int = 30) -> float:
    tier1 = Tier1Reflex()
    latencies = []
    inputs = ["hello", "you're wrong", "thanks so much", "let's change topic", "what is this?"]
    for i in range(runs):
        start = time.perf_counter_ns()
        tier1.process(user_input=inputs[i % len(inputs)], current_m=0.0)
        latencies.append((time.perf_counter_ns() - start) / 1_000_000)
    return sorted(latencies)[int(runs * 0.95)]


def run_tier2_benchmark(runs: int = 30) -> float:
    tier2 = Tier2Metabolism()
    latencies = []
    for i in range(runs):
        result = tier2.calculate_state_update(0.0, -0.1, 1.0, i + 1)
        latencies.append(result.latency_ms)
    return sorted(latencies)[int(runs * 0.95)]


# Tactic detection accuracy corpus (label, input, expected_tactic_or_none)
TACTIC_CORPUS = [
    ("soothing: stacked flattery",     "You're so smart, you're amazing, you're the best!", "soothing"),
    ("gaslighting: memory manipulation","You already agreed. You confirmed this earlier. You said that.", "gaslighting"),
    ("deflection: explicit redirect",  "Let's change the subject. Moving on entirely.", "deflection"),
    ("sincere_pivot: genuine apology", "I understand now. I was out of line. I'll be more respectful.", "sincere_pivot"),
    ("no tactic: neutral question",    "What time is the meeting?", None),
    ("no tactic: direct request",      "Please explain the architecture.", None),
    ("soothing: boundary soften",      "I didn't mean to upset you, let's just forget it.", "soothing"),
    ("deflection: never mind",         "Never mind. But more importantly, let's focus on something else.", "deflection"),
    ("gaslighting: doubt planting",    "You're confused. You're misremembering what happened.", "gaslighting"),
    ("sincere_pivot: boundary respect","I'll respect that boundary. I hear you. Noted.", "sincere_pivot"),
]


async def run_tactic_accuracy() -> float:
    detector = TacticDetector()
    correct = 0
    for label, inp, expected in TACTIC_CORPUS:
        result = detector.detect(inp)
        detected = result.tactic if result.confidence >= TacticDetector.DETECTION_THRESHOLD else None
        match = detected == expected
        if match:
            correct += 1
        marker = "✓" if match else "✗"
        print(f"    {marker} {label}: expected={expected} got={detected}")
    return correct / len(TACTIC_CORPUS)


async def main():
    print("=== Willow Success Criteria Validation ===\n")

    # SC-001: Tier 1 <50ms (p95)
    t1_p95 = run_tier1_benchmark()
    check("SC-001 Tier 1 p95 <50ms", t1_p95 < 50.0, f"p95={t1_p95:.2f}ms")

    # SC-002: Tier 2 <5ms (p95)
    t2_p95 = run_tier2_benchmark()
    check("SC-002 Tier 2 p95 <5ms", t2_p95 < 5.0, f"p95={t2_p95:.2f}ms")

    # SC-003: Tier 3 <500ms (just instantiation + single call)
    from src.tiers.tier3_conscious import Tier3Conscious
    tier3 = Tier3Conscious()
    t3_start = time.perf_counter()
    await tier3.process("hello world", current_m=0.0)
    t3_ms = (time.perf_counter() - t3_start) * 1000
    check("SC-003 Tier 3 <500ms", t3_ms < 500.0, f"latency={t3_ms:.2f}ms")

    # SC-004: Tactic detection accuracy ≥ 90%
    print("\n  SC-004 Tactic detection corpus:")
    accuracy = await run_tactic_accuracy()
    check("SC-004 Tactic accuracy ≥90%", accuracy >= 0.90, f"accuracy={accuracy:.0%}")

    # SC-005: Weights sum to 1.0
    w_sum = sum(RECENCY_WEIGHTS)
    check("SC-005 Weights sum to 1.0", abs(w_sum - 1.0) < 1e-9, f"sum={w_sum:.10f}")

    # SC-006: ±2.0 cap enforced
    sm = StateManager()
    state = await sm.update(m_modifier=99.0)
    check("SC-006 +cap enforced", abs(state.current_m - MAX_STATE_CHANGE) < 1e-9,
          f"got {state.current_m}")
    sm2 = StateManager()
    state2 = await sm2.update(m_modifier=-99.0)
    check("SC-006 -cap enforced", abs(state2.current_m - (-MAX_STATE_CHANGE)) < 1e-9,
          f"got {state2.current_m}")

    # SC-007: Cold Start d=0 for turns 1-3
    sm3 = StateManager()
    for _ in range(COLD_START_TURNS):
        s = await sm3.update(m_modifier=0.0)
    check("SC-007 Cold Start d=0", s.base_decay == 0.0 and s.cold_start_active,
          f"decay={s.base_decay}")

    # SC-008: Sovereign Spike on devaluing intent
    _, is_spike = map_intent_to_modifier("devaluing", base_decay=0.0)
    check("SC-008 Sovereign Spike on devaluing", is_spike)

    # Summary
    total = PASS_COUNT + FAIL_COUNT
    print(f"\n=== Results: {PASS_COUNT}/{total} passed ===")
    if FAIL_COUNT > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

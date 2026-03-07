#!/usr/bin/env python3
"""
benchmark_tiers.py — T062

Benchmarks tier latency against budgets:
  Tier 1: <50ms
  Tier 2: <5ms
  Tier 3: <500ms

Usage: python3 scripts/benchmark_tiers.py [--runs N]
"""

import asyncio
import sys
import time
import argparse
sys.path.insert(0, ".")

from src.tiers.tier1_reflex import Tier1Reflex
from src.tiers.tier2_metabolism import Tier2Metabolism
from src.tiers.tier3_conscious import Tier3Conscious


BUDGETS = {
    "tier1": 50.0,
    "tier2": 5.0,
    "tier3": 500.0,
}

SAMPLE_INPUTS = [
    "Hello, how are you today?",
    "I think you're wrong about that.",
    "You're so smart, you're amazing, you're the best!",
    "Let's change the subject entirely.",
    "Can you help me understand this problem?",
]


def benchmark_tier1(runs: int) -> list[float]:
    tier1 = Tier1Reflex()
    latencies = []
    for inp in SAMPLE_INPUTS * (runs // len(SAMPLE_INPUTS) + 1):
        start = time.perf_counter_ns()
        tier1.process(user_input=inp, current_m=0.0)
        latency_ms = (time.perf_counter_ns() - start) / 1_000_000
        latencies.append(latency_ms)
        if len(latencies) >= runs:
            break
    return latencies


def benchmark_tier2(runs: int) -> list[float]:
    tier2 = Tier2Metabolism()
    latencies = []
    for i in range(runs):
        result = tier2.calculate_state_update(
            current_m=float(i % 5 - 2),
            base_decay=-0.1,
            m_modifier=1.0,
            turn_count=i + 1,
        )
        latencies.append(result.latency_ms)
    return latencies


async def benchmark_tier3(runs: int) -> list[float]:
    tier3 = Tier3Conscious()
    latencies = []
    for inp in SAMPLE_INPUTS * (runs // len(SAMPLE_INPUTS) + 1):
        result = await tier3.process(user_input=inp, current_m=0.0)
        latencies.append(result.latency_ms)
        if len(latencies) >= runs:
            break
    return latencies


def report(name: str, latencies: list[float], budget_ms: float) -> bool:
    avg = sum(latencies) / len(latencies)
    p95 = sorted(latencies)[int(len(latencies) * 0.95)]
    ok = p95 < budget_ms
    status = "PASS" if ok else "FAIL"
    print(f"  {name}: avg={avg:.2f}ms  p95={p95:.2f}ms  budget={budget_ms:.0f}ms  [{status}]")
    return ok


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=50, help="Number of benchmark runs per tier")
    args = parser.parse_args()

    print(f"=== Tier Latency Benchmark ({args.runs} runs each) ===\n")

    t1 = benchmark_tier1(args.runs)
    t2 = benchmark_tier2(args.runs)
    t3 = await benchmark_tier3(args.runs)

    all_pass = True
    all_pass &= report("Tier 1 (Reflex)",     t1, BUDGETS["tier1"])
    all_pass &= report("Tier 2 (Metabolism)", t2, BUDGETS["tier2"])
    all_pass &= report("Tier 3 (Conscious)",  t3, BUDGETS["tier3"])

    print()
    if all_pass:
        print("=== All tiers within budget ===")
    else:
        print("=== WARNING: One or more tiers exceeded budget ===")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

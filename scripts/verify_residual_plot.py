#!/usr/bin/env python3
"""
verify_residual_plot.py — T062

Verifies ResidualPlot behaviour:
- 5-turn rolling window
- Weights sum to 1.0
- Weighted average calculation

Usage: python3 scripts/verify_residual_plot.py
"""

import sys
sys.path.insert(0, ".")

from src.core.residual_plot import ResidualPlot, RECENCY_WEIGHTS


def main():
    print("=== ResidualPlot Verification ===\n")
    plot = ResidualPlot()

    # 1. Weights
    total = sum(RECENCY_WEIGHTS)
    ok = abs(total - 1.0) < 1e-9
    print(f"Weights: {RECENCY_WEIGHTS}")
    print(f"Sum: {total:.10f}  {'OK' if ok else 'FAIL'}\n")
    if not ok:
        sys.exit(1)

    # 2. Rolling window — values must be within ±2.0
    values = [1.0, 2.0, -1.0, 0.5, 1.5, -0.5]
    for v in values:
        plot.add_turn(v)

    print(f"After {len(values)} additions (rolling window=5):")
    print(f"  m_values: {plot.m_values}")
    assert len(plot.m_values) == 5, f"Expected 5 turns, got {len(plot.m_values)}"
    print(f"  length: {len(plot.m_values)}  OK\n")

    # 3. Weighted average
    avg = plot.weighted_average_m
    print(f"Weighted average: {avg:.4f}")
    # Most recent value (-0.5) has highest weight — average should be in [-1.0, 1.5]
    assert -1.0 <= avg <= 1.5, f"Average {avg} outside expected range [-1, 1.5]"
    print(f"  Within [-1.0, 1.5]: OK\n")

    # 4. Uniform values (within ±2.0 cap)
    plot2 = ResidualPlot()
    for _ in range(5):
        plot2.add_turn(1.5)
    avg2 = plot2.weighted_average_m
    assert abs(avg2 - 1.5) < 1e-6, f"Uniform average {avg2} != 1.5"
    print(f"Uniform 1.5 × 5 → average: {avg2:.6f}  OK")

    print("\n=== All checks passed ===")


if __name__ == "__main__":
    main()

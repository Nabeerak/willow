---
id: 0008
title: Tier 2 Metabolism Implementation
stage: green
date: 2026-03-01
surface: agent
model: claude-opus-4-5-20251101
feature: 001-willow-behavioral-framework
branch: 001-willow-behavioral-framework
user: nabeera
command: implement T021
labels: [tier2,metabolism,state-formula,implementation]
links:
  spec: null
  ticket: T021
  adr: null
  pr: null
files:
  - src/tiers/tier2_metabolism.py
  - src/tiers/__init__.py
tests:
  - inline verification tests passed
---

## Prompt

Implement T021: Tier 2 Metabolism in /home/nabeera/willow/src/tiers/tier2_metabolism.py

Create a Tier2Metabolism class that handles:
1. State formula: a_{n+1} = a_n + d + m
2. Latency budget: <5ms
3. Cold Start logic: d=0 for turns 1-3

Features:
- calculate_state_update(current_m: float, base_decay: float, m_modifier: float, turn_count: int) -> float: Apply state formula
- apply_cold_start(turn_count: int) -> float: Return 0 if turn_count <= 3, else base_decay
- clamp_modifier(m_modifier: float) -> float: Enforce +/-2.0 cap
- calculate_sovereign_spike(base_decay: float) -> float: Return -(base_decay + 5.0) for devaluing intent

Constants:
- COLD_START_TURNS = 3
- MAX_STATE_CHANGE = 2.0
- BASE_DECAY_RATE = -0.1

Requirements:
- Must complete in <5ms
- Use timestamps to track latency
- Pure mathematical operations

Tech stack: Python 3.11+

## Response snapshot

Created complete Tier2Metabolism implementation with:
- Tier2Metabolism dataclass with all required methods
- MetabolismResult dataclass for returning calculation results with latency tracking
- Module-level constants: COLD_START_TURNS=3, MAX_STATE_CHANGE=2.0, BASE_DECAY_RATE=-0.1, LATENCY_BUDGET_MS=5.0
- State formula implementation: a_{n+1} = a_n + d + m
- Cold start logic suppressing decay for turns 1-3
- Modifier clamping to +/-2.0 range
- Sovereign spike calculation for devaluing intent
- Nanosecond-precision latency tracking using time.perf_counter_ns()
- Updated __init__.py to export all public symbols

All verification tests passed with sample latency of ~0.001ms, well within 5ms budget.

## Outcome

- Impact: T021 fully implemented with all required features
- Tests: All inline verification tests passed
- Files: Created src/tiers/tier2_metabolism.py, updated src/tiers/__init__.py
- Next prompts: Add unit tests, integrate with Tier system
- Reflection: Pure mathematical operations ensure consistent sub-millisecond latency

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): PASS - all assertions passed
- Prompt variant (if applicable): direct implementation request
- Next experiment (smallest change to try): add formal pytest test file

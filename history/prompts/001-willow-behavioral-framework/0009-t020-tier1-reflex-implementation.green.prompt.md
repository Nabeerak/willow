---
id: 0009
title: T020 Tier 1 Reflex Implementation
stage: green
date: 2026-03-01
surface: agent
model: claude-opus-4-5-20251101
feature: 001-willow-behavioral-framework
branch: 001-willow-behavioral-framework
user: nabeera
command: implement
labels: ["tier1", "reflex", "tone-mirroring", "latency"]
links:
  spec: null
  ticket: T020
  adr: null
  pr: null
files:
  - src/tiers/tier1_reflex.py
  - src/tiers/__init__.py
tests:
  - Manual import verification
  - Tone detection tests (5 tone types)
  - m-value calibration tests
  - Response prefix generation tests
  - Latency budget verification (<50ms)
  - Serialization tests
---

## Prompt

Implement T020: Tier 1 Reflex in /home/nabeera/willow/src/tiers/tier1_reflex.py

Create a Tier1Reflex class that handles:
1. Tone mirroring - match user's emotional tone in response
2. Latency budget: <50ms
3. Immediate response generation

Features:
- mirror_tone(user_input: str, current_m: float) -> str: Generate tone-appropriate response prefix
- get_tone_markers(user_input: str) -> dict: Extract tone indicators
- apply_tone_to_response(response: str, tone: str) -> str: Adjust response tone

Tone types (from ThoughtSignature): warm, casual, formal, sarcastic, aggressive
- High m (>0): Allow warmer, more casual responses with analogies
- Low m (<0): More formal, concise responses
- Neutral m (=0): Balanced, professional tone

Requirements:
- Must complete in <50ms
- Use timestamps to track latency
- Simple heuristics, no heavy ML

Tech stack: Python 3.11+, async/await patterns

Create the complete implementation. Do not use placeholder comments.

## Response snapshot

Created `/home/nabeera/willow/src/tiers/tier1_reflex.py` with full implementation of Tier1Reflex class:

**Key components:**
- `Tier1Reflex` class: Main processor for reflexive tone mirroring
- `ToneMarkers` dataclass: Captures detected tone indicators with confidence scores
- `ReflexResult` dataclass: Full processing result with latency tracking

**Methods implemented:**
- `get_tone_markers(user_input)`: Regex-based tone detection (warm, casual, formal, sarcastic, aggressive)
- `mirror_tone(user_input, current_m)`: Generate tone-appropriate response prefix
- `apply_tone_to_response(response, tone)`: Adjust response text with tone markers
- `process(user_input, current_m, base_response)`: Full pipeline with latency tracking
- `quick_prefix(tone, current_m)`: Fast path when tone is already known
- `calibrate_tone(detected_tone, current_m)`: Adjust tone based on m-value

**Latency performance:**
- Average processing time: ~0.032ms (well under 50ms budget)
- Budget tracking with `budget_exceeded` flag in results

## Outcome

- Impact: Tier 1 reflex layer implemented - enables real-time tone mirroring for responsive conversational behavior
- Tests: All manual tests pass - tone detection, calibration, prefix generation, latency budget
- Files: 2 files (1 created, 1 modified)
- Next prompts: Integration with Tier 2/3, end-to-end conversation flow
- Reflection: Simple regex heuristics sufficient for <50ms; no ML needed for MVP

## Evaluation notes (flywheel)

- Failure modes observed: None - all tests pass
- Graders run and results (PASS/FAIL): Manual verification PASS
- Prompt variant (if applicable): N/A
- Next experiment (smallest change to try): Add async wrapper if needed for pipeline integration

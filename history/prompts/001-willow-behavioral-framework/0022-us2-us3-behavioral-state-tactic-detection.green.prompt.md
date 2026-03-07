---
id: 0022
title: US2 Behavioral State + US3 Tactic Detection Implementation
stage: green
date: 2026-03-03
surface: agent
model: claude-sonnet-4-6
feature: 001-willow-behavioral-framework
branch: 002-gemini-audio-opt
user: nabeera
command: continue (implement US2 T027-T032 and US3 T033-T040 after background agents failed permissions)
labels: ["us2", "us3", "warm-sharp", "tactic-detector", "tier3", "tier4", "t027", "t028", "t029", "t030", "t031", "t032", "t033", "t034", "t035", "t036", "t037", "t038", "t039", "t040"]
links:
  spec: specs/001-willow-behavioral-framework/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - src/persona/__init__.py
  - src/persona/warm_sharp.py
  - src/signatures/tactic_detector.py
  - src/tiers/tier3_conscious.py
  - src/tiers/tier4_sovereign.py
  - src/tiers/tier2_metabolism.py
  - src/tiers/tier1_reflex.py
  - src/tiers/__init__.py
  - src/signatures/__init__.py
  - src/core/state_manager.py
  - src/main.py
  - specs/001-willow-behavioral-framework/tasks.md
tests:
  - tests/unit/test_us1_natural_voice.py (91 tests, all pass — zero regressions)
  - tests/unit/test_sovereign_truth_cache.py (40 tests, all pass)
---

## Prompt

continue (resume from context: phase 2 tasks marked complete, implement US2 T027-T032 and US3 T033-T040 — background agents had failed with permission denials)

## Response snapshot

Implemented US2 (T027-T032) and US3 (T033-T040) in sequence:

**Phase 2 cleanup first:**
- Marked T010-T013 and T070-T075 as [x] in tasks.md — code was implemented and tests passing (91/91) but checkboxes were unchecked.

**US2 — Behavioral State Response (T027-T032):**
- **T027**: `src/persona/warm_sharp.py` — WarmSharp persona with three m-zones: `high_m` (>0.5) openers + analogy pool, `neutral_m` balanced, `low_m` concise. `get_response_style()` returns `ResponseStyle(max_sentences, use_analogy, opener)`.
- **T028**: `src/tiers/tier1_reflex.py` — Added `get_warm_sharp_prefix(current_m)` and `apply_persona_tells(response, current_m)` methods. `_generate_response` in `main.py` now uses WarmSharp opener as baseline, applies behavioral tells.
- **T029**: `src/tiers/tier2_metabolism.py` — Added `INTENT_MODIFIERS` dict (collaborative=+1.5, neutral=0, hostile=-0.5, devaluing=-2.0 clamped) and `map_intent_to_modifier(intent, base_decay)` function. Devaluing returns `(-(base_decay+5.0), True)` — sovereign spike formula.
- **T030**: `src/persona/warm_sharp.py` — `apply_behavioral_tells(response, current_m)`: high_m appends analogy from ANALOGY_POOL (5 entries, deterministic index); low_m truncates to first sentence.
- **T031**: Already implemented in `StateManager.update()` — confirmed present, checked off.
- **T032**: `src/core/state_manager.py` — Added `logging.debug()` in `update()` method: logs turn, m_modifier, capped_m, current_m, sovereign_spike, troll_defense flags.

**US3 — Tactic Detection and Response (T033-T040):**
- **T033**: `src/signatures/tactic_detector.py` — `TacticDetector` class with 5 detectors + `detect()` dispatcher. Confidence-based, threshold=0.40. Priority: gaslighting > soothing > deflection > contextual_sarcasm > mirroring.
- **T034**: `src/tiers/tier3_conscious.py` — `Tier3Conscious.process()` async method: intent classification (keyword heuristics), tone classification, tactic detection, [THOUGHT] tag merge, ThoughtSignature construction. Returns `Tier3Result`.
- **T035**: `src/tiers/tier4_sovereign.py` — `Tier4Sovereign.execute(truth, active_task)` implements full 6-step sequence. `check_and_execute()` runs all 3 gates before execute. Vacuum mode: stores `response_on_return` on SessionState, skips speech.
- **T036**: `src/signatures/tactic_detector.py` — `detect_contextual_sarcasm()`: `weighted_average_m > 0` → humor (tactic=contextual_sarcasm); `≤ 0` → malice (tactic=gaslighting, is_malice=True).
- **T037**: Already in `Tier2Metabolism.calculate_sovereign_spike()` — confirmed present, added `map_intent_to_modifier()` as public API.
- **T038**: `src/main.py` — `_process_tier3()` and `_process_tier4()` replaced with real Tier3Conscious and Tier4Sovereign calls. Both run via `asyncio.create_task` (non-blocking).
- **T039**: `src/tiers/tier3_conscious.py` — `logger.debug()` on every ThoughtSignature with intent, tone, tactic, m_modifier, tier_trigger, rationale, latency.
- **T040**: `src/main.py` — `_extract_thought_tag(raw_response)` using `extract_thought()` + `extract_surface()` from parser.py. `_process_tier3()` accepts `thought_tag_data` kwarg for merge.

**Fixes applied:**
- Sovereign spike raw value (-5.0) exceeded ±2.0 validation on `ConversationalTurn` and `ThoughtSignature` — clamped in `_create_turn_record()`.
- Coroutine factory pattern: `check_and_execute()` changed to accept `tier3_intent_factory` (callable) not `tier3_intent_coro` (pre-created awaitable) to avoid "never awaited" warning when early gates abort.
- `SessionState.response_on_return: Optional[str]` field added for vacuum mode return delivery.
- `StateManager.set_response_on_return()` and `consume_response_on_return()` added.

## Outcome

- ✅ Impact: US2 + US3 fully implemented — Warm but Sharp persona, 5-tactic detector, Tier 3 Conscious, Tier 4 Sovereign, all wired in main.py
- 🧪 Tests: 91/91 passing, zero regressions
- 📁 Files: 11 modified/created
- 🔁 Next: Human Gate 2 (template voice review) → then US4 T041-T046 + US5 T047-T052 in parallel

## Evaluation notes (flywheel)

- Failure modes observed: Sovereign spike -5.0 exceeded ±2.0 field validation on ConversationalTurn and ThoughtSignature (2 locations) — fixed with clamping in _create_turn_record. Coroutine "never awaited" warning — fixed by switching to lazy factory pattern.
- Graders run and results (PASS/FAIL): pytest 91/91 PASS
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): Human Gate 2 (review Warm but Sharp response templates), then proceed US4+US5 in parallel

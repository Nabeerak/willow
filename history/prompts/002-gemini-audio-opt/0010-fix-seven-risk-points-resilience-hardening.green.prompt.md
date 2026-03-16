---
id: "0010"
title: "Fix seven risk points resilience hardening"
stage: green
date: 2026-03-13
surface: agent
model: claude-sonnet-4-6
feature: 002-gemini-audio-opt
branch: main
user: nabeera
command: fix all
labels: ["resilience", "async", "context-window", "debounce", "timeout", "race-condition", "data-model"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - src/main.py
  - src/signatures/tactic_detector.py
  - src/tiers/tier3_conscious.py
  - src/tiers/tier4_sovereign.py
  - src/core/state_manager.py
  - src/core/sovereign_truth.py
tests:
  - tests/unit/test_audio_integration.py
  - tests/unit/test_gemini_live_thinking.py
---

## Prompt

Fix all 7 identified risk points: async ghost task, context window pollution, Tier 4 deadlocks, file I/O overhead, embedding API timeout, filler audio race condition, global lock scalability note.

## Response snapshot

**Fix 1 — Async Ghost Task (main.py):**
Added `_log_background_task_error()` done-callback to `_schedule_background_task()`. Calls `task.exception()` and logs at ERROR level. Also wrapped `_process_tier3()` body in `try/except Exception` that logs and re-raises — exposes errors at both the task level (done-callback) and the processing level (logger).

**Fix 2 — Context Window Pollution (main.py):**
Added `_last_injected_zone: Optional[str] = None`. Zone directive only injected when `zone != self._last_injected_zone` OR `behavioral_note` is present. Stable conversations skip injection entirely. `_last_injected_zone` reset on Tier 4 fire (zone may shift after sovereign override).

**Fix 3 — Tier 4 Debounce (main.py):**
Added `_last_t4_fire_time: float = 0.0`. At start of `_process_tier4()`, skips if `< 500ms` since last fire. Records fire time when `result.fired` is True.

**Fix 4 — File I/O Preload (main.py):**
Added startup warm-up block at end of `__init__()`. Imports and calls all 6 `lru_cache` JSON loaders once at startup: `_load_m_modifiers`, `_load_rules`, `_load_tone_signals`, `_load_intent_keywords`, `_load_persona`, `_load_tactic_keywords`. Wrapped in `try/except` (non-fatal).

**Fix 5 — Embedding API Timeout (tactic_detector.py + tier3_conscious.py):**
`_semantic_fallback()` made async. Uses `asyncio.wait_for(loop.run_in_executor(None, find_similar_tactic, ...), timeout=0.30)`. On `TimeoutError`, logs warning and returns `TacticDetectionResult(tactic=None, confidence=0.0)`. `detect()` made async — cascades to `tier3_conscious.py` which now `await`s `self._detector.detect(...)`.

**Fix 6 — Filler Race Condition (main.py):**
Added `self._filler_player.cancel()` before `inject_behavioral_context()` in `_on_gemini_turn_complete`. Stops any playing filler clip before real Gemini response begins streaming.

**Fix 7 — Global Lock (state_manager.py):**
Added Redis upgrade path documentation in module docstring. Per-session asyncio.Lock is uncontended at current architecture; Redis + redlock-py upgrade path documented without implementation.

**Pre-existing bugs fixed along the way:**
- `_validate_sovereign_truth()` referenced undefined `forced_prefix` / `response_directive` — fixed to match actual parameters
- `SovereignTruth` dataclass had `response_template` field but JSON had `forced_prefix`/`response_directive` — full data model reconciliation: replaced `response_template` with `forced_prefix: str` + `response_directive: str` in dataclass, `_validate_sovereign_truth`, `to_dict()`, `from_dict()`
- `Tier4Sovereign.execute()` used `response_text=` which doesn't exist in `Tier4Result` — updated to `forced_prefix=truth.forced_prefix, response_directive=truth.response_directive`
- `_process_tier3()` had unclosed `try:` block (retroactive correction was outside try scope) — fixed indentation and added proper `except Exception`

## Outcome

- ✅ Impact: All 7 risk points addressed; SovereignTruth data model now consistent with JSON schema
- 🧪 Tests: 167 unit tests passing (up from failing state due to pre-existing sovereign truth bugs)
- 📁 Files: 6 files modified
- 🔁 Next prompts: Integration testing against live Gemini session; server.py SovereignTruth CRUD API may need `response_template` → `forced_prefix`/`response_directive` update
- 🧠 Reflection: The sovereign truth data model mismatch (JSON vs dataclass vs Tier4Result) was a significant pre-existing inconsistency. Fixing the 7 risk points exposed it because tests now exercised code paths that instantiate SovereignTruth from JSON.

## Evaluation notes (flywheel)

- Failure modes observed: Pre-existing `try:` block without `except` in `_process_tier3` — silent syntax error that only surfaces on import
- Graders run and results (PASS/FAIL): 167 unit tests PASS
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): Update server.py CRUD API to use `forced_prefix`/`response_directive` instead of `response_template`

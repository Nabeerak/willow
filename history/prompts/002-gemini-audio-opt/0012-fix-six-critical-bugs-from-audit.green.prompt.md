---
id: "0012"
title: Fix Six Critical Bugs from Audit
stage: green
date: 2026-03-14
surface: agent
model: claude-sonnet-4-6
feature: 002-gemini-audio-opt
branch: main
user: nabeera
command: continuation
labels: ["bugfix", "audit", "resilience", "filler-audio", "tier4", "gemini-live"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - src/main.py
  - src/voice/gemini_live.py
  - src/voice/filler_audio.py
  - tests/unit/test_audio_integration.py
  - tests/unit/test_sovereign_truth_cache.py
tests:
  - tests/ (236 passed, 0 failed)
---

## Prompt

7 and 8 will be resolved by gemini itself you may start with 1 to 6

(Continuation from previous session — implementing fixes 1-6 from external 30-question security/architecture audit)

## Response snapshot

Implemented all 6 critical bug fixes identified by the external audit. Several were already partially addressed by the linter between sessions:

**Fix 1 — reset_turn_flags at wrong location**: Removed stale `reset_turn_flags()` call at end of `process_turn()` (line ~1136). The correct call at the START of `process_turn()` was already added in the prior session. This prevents `audio_started` from the previous turn blocking the current turn's Tier 4 fire (FR-022).

**Fix 2 — Deferred contradictions as background task**: Already fixed by linter (inline `await` + `TurnResult` return with `forced_prefix`/`response_directive`). Updated stale comment that still said "background task."

**Fix 3 — `_turn_complete_fired` never set/reset**: Linter already added `self._turn_complete_fired = True` in `_handle_turn_complete()`. Added `self._turn_complete_fired = False` to the next-turn reset block so the flag doesn't persist across turns.

**Fix 4 — `_handle_turn_complete` blocking receive loop**: Already fixed by linter — wrapped in `asyncio.create_task()` at line 880.

**Fix 5 — `is_agent_speaking` not toggled during filler**: Already fixed by linter — `start_agent_speaking()` called before `_filler_player.play()` at line 1100.

**Fix 6 — Filler sends entire PCM in single frame**: Linter chunked to 50ms. Tightened to 20ms (640-byte) chunks for more responsive cancellation on barge-in.

Also fixed 2 broken tests caused by linter's `active_task→streaming_session` rename: `test_audio_integration.py` (4 occurrences) and `test_sovereign_truth_cache.py` (rewrote `TestHardExit` to use mock streaming session instead of asyncio.Task).

## Outcome

- ✅ Impact: All 6 critical bugs from external audit resolved; 236/236 tests passing
- 🧪 Tests: 236 passed, 0 failed; fixed 2 test files with stale `active_task` references
- 📁 Files: 5 files modified (3 source, 2 test)
- 🔁 Next prompts: End-to-end integration test with live Gemini session; bugs 7-8 deferred to Gemini SDK
- 🧠 Reflection: The linter independently fixed 4 of 6 bugs between sessions, requiring only comment updates and minor tightening. The test breakage from linter renames was the main new work.

## Evaluation notes (flywheel)

- Failure modes observed: Linter renames (`active_task→streaming_session`) broke tests without updating them; 50ms filler chunks still coarser than ideal for barge-in responsiveness
- Graders run and results (PASS/FAIL): pytest 236/236 PASS
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): Run live Gemini session to verify Tier 4 forced_prefix injection and filler chunking work end-to-end

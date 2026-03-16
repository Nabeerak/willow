---
id: "0011"
title: "Fix content bloating memory depletion risks"
stage: green
date: 2026-03-13
surface: agent
model: claude-sonnet-4-6
feature: 002-gemini-audio-opt
branch: main
user: nabeera
command: fix all
labels: ["memory", "bloat", "cap", "session-age", "server-crud", "persona-watcher"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - src/server.py
  - src/main.py
  - src/core/session_memory.py
tests:
  - tests/unit/test_audio_integration.py
  - tests/unit/test_gemini_live_thinking.py
---

## Prompt

not only 4 but all of them — fix all items from the content bloating / memory depletion risk report:
1. server.py CRUD broken (response_template → forced_prefix/response_directive)
2. _watch_persona_file dead code (wire up or delete)
3. _turn_history unbounded (cap to 50)
4. _conversation_messages unbounded (cap to 20)
5. Gemini Live context window accumulation (session age tracking + warning)
6. UserMemory.sessions unbounded (cap to 20)

## Response snapshot

**Fix 1 — server.py CRUD (update_truth):**
Replaced `response_template=(body.response_template if ... else existing.response_template)` with two separate fields: `forced_prefix=body.forced_prefix if body.forced_prefix is not None else existing.forced_prefix` and `response_directive=body.response_directive if body.response_directive is not None else existing.response_directive`. `TruthCreate` and `TruthUpdate` Pydantic models already fixed in prior session; only the PUT constructor call remained.

**Fix 2 — _watch_persona_file wired up:**
Added `self._schedule_background_task(self._watch_persona_file())` at the end of `start_session()` (before the return). The watcher polls every 2s for mtime change on `data/willow_persona.json` and calls `_load_persona.cache_clear()` + `_load_tone_signals.cache_clear()` on change. No persona file = watcher sleeps silently.

**Fix 3 — _turn_history cap (50):**
Added `if len(self._turn_history) > 50: self._turn_history = self._turn_history[-50:]` immediately after `self._turn_history.append(turn)` in `handle_user_input()`.

**Fix 4 — _conversation_messages cap (20):**
Added cap guard at both append sites: `_process_tier4()` result path (line ~1306) and `_evaluate_deferred_contradictions()` result path (line ~1353). Guard: `if len(self._conversation_messages) > 20: self._conversation_messages = self._conversation_messages[-20:]`.

**Fix 5 — Gemini Live session age warning:**
Added `_session_start_dt: Optional[datetime] = None` to `__init__`. In `start_session()`, captures `_now = datetime.now()` and sets both `_session_start_time = _now.isoformat()` and `_session_start_dt = _now`. In `handle_user_input()`, checks age in minutes at every turn — if >= 90min, logs WARNING and sends `send_client_command("session_age_warning", age_minutes=...)` to the browser. Note: Gemini Live context accumulates natively on the API side; this warning is the only viable mitigation.

**Fix 6 — UserMemory.sessions cap (20):**
Added `if len(self.sessions) > 20: self.sessions = self.sessions[-20:]` in `UserMemory.add_session()` in `session_memory.py`, immediately after `self.sessions.append(summary)`.

## Outcome

- ✅ Impact: All 6 content bloating / memory depletion risks resolved; server.py CRUD is now consistent with the SovereignTruth data model
- 🧪 Tests: 167 unit tests passing (unchanged)
- 📁 Files: 3 files modified (src/server.py, src/main.py, src/core/session_memory.py)
- 🔁 Next prompts: Integration test against live Gemini session; verify session_age_warning surfaces in dashboard; verify persona hot-reload fires when willow_persona.json is edited
- 🧠 Reflection: Gemini Live context accumulation is architecturally uncontrollable from the Python side — the warning approach is the correct boundary. All other items were simple list caps that should have been in place from initial implementation.

## Evaluation notes (flywheel)

- Failure modes observed: None — all 6 fixes applied cleanly; no existing tests broken
- Graders run and results (PASS/FAIL): 167 unit tests PASS
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): Add a dashboard indicator that renders the session_age_warning command (orange banner at 90min, red at 120min)

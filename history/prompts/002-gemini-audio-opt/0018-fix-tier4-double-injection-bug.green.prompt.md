---
id: "0018"
title: Fix tier4 double injection bug
stage: green
date: 2026-03-15
surface: agent
model: claude-sonnet-4-6
feature: 002-gemini-audio-opt
branch: main
user: nabeera
command: /sp.phr
labels: ["tier4", "double-injection", "context-depletion", "behavioral-pipeline", "sovereign-truth", "single-source-of-truth"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - src/tiers/tier4_sovereign.py
  - src/main.py
tests:
  - tests/unit/ (171 passed)
---

## Prompt

Fix the double-injection bug only.
Do not touch anything else.

THE BUG:
tier4_sovereign.py:161 fires a sovereign truth injection.
main.py:697-701 fires another injection for the same turn.
Result: Gemini receives two conflicting [SYS] directives for
the same Tier 4 event. One from the truth file, one from the
orchestrator. They accumulate as separate synthetic turns.

FIND:
1. Read tier4_sovereign.py:161 — what exactly is injected?
2. Read main.py:697-701 — what exactly is injected?
3. Are they sending the same content or different content?
4. Which one should be the single source of truth?

FIX:
One injection per Tier 4 event. Not two.

If tier4_sovereign.py handles the injection directly:
- Remove the injection at main.py:697-701
- Add a flag: tier4_result.injection_sent = True
- In main.py, check that flag before injecting

If main.py should own all injections:
- Remove the injection from tier4_sovereign.py:161
- Ensure main.py:697-701 sends the complete payload

The right choice: main.py owns all injections.
All context injection happens in one place.
tier4_sovereign.py returns a result, never injects directly.

After fix:
1. Add log: logger.info("T4 INJECTION SENT: single")
   Confirm it appears exactly once per Tier 4 event.
2. Run: python -m pytest tests/unit/ -x -q 2>&1 | tail -10
3. Show me the injection point before and after.
4. If any test breaks, stop and show me the failure.

## Response snapshot

Both injection calls confirmed and compared: tier4_sovereign.py:161 sent `'You MUST begin your next response exactly with: "{forced_prefix}" {response_directive}'`; main.py:712 sent `'{response_directive} Begin your next response exactly with: "{forced_prefix}"'` — same data, different word order, both firing per T4 event. Removed the inject_behavioral_context() call from tier4_sovereign.py entirely (kept the interrupt() call). main.py remains the single injection point. Added `logger.info("T4 INJECTION SENT: single")` after the inject call. 171 unit tests pass.

## Outcome

- ✅ Impact: Double-injection bug fixed. Every T4 event now produces exactly one [SYS] synthetic turn in Gemini's context instead of two. Eliminates the #1 ranked depletion risk from AUDIT 3. tier4_sovereign.py now owns only interruption; main.py owns all behavioral context injection.
- 🧪 Tests: tests/unit/ — 171 PASS
- 📁 Files: src/tiers/tier4_sovereign.py, src/main.py
- 🔁 Next prompts: Commit all accumulated changes; live test to confirm T4 INJECTION SENT: single appears once per sovereign trigger in logs
- 🧠 Reflection: The two injections had subtly different wording (forced_prefix and response_directive swapped in ordering) — not just a duplicate but potentially conflicting instructions to Gemini. The fix was surgical: one removal, one log line, zero behavioral change.

## Evaluation notes (flywheel)

- Failure modes observed: main.py was modified by the IDE/linter between reads during this session — required re-read before final edit to avoid overwrite collision
- Graders run and results (PASS/FAIL): tests/unit/ — 171 PASS
- Prompt variant (if applicable): find + diagnose + fix (single focused bug)
- Next experiment (smallest change to try): Add a unit test that mocks inject_behavioral_context and asserts it is called exactly once when Tier 4 fires

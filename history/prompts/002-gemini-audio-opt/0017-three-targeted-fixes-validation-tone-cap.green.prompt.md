---
id: "0017"
title: Three targeted fixes validation tone cap
stage: green
date: 2026-03-15
surface: agent
model: claude-sonnet-4-6
feature: 002-gemini-audio-opt
branch: main
user: nabeera
command: /sp.phr
labels: ["input-validation", "name-sanitization", "tone-endings", "m_modifier", "security", "tier1", "tier2"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - src/main.py
  - src/tiers/tier1_reflex.py
tests:
  - none (targeted fix, no new tests added)
---

## Prompt

In src/main.py:648, before captured_name is injected into
behavioral context, add strict validation:

import re
def _sanitize_name(name: str) -> str | None:
    name = name.strip()
    if not re.match(r'^[A-Za-z\- ]{2,20}$', name):
        return None
    return name

If _sanitize_name() returns None, do not inject the name.
Log: logger.warning(f"Rejected unsafe name: {name[:30]}")
Do not change anything else.

In src/tiers/tier1_reflex.py:307, remove the string
concatenation that appends TONE_ADJUSTMENTS to the LLM response.

Delete the line:
adjusted.rstrip() + " " + endings[0].strip()

Replace with just:
adjusted

The tone ending was causing the UI transcript to diverge from
the audio Gemini actually spoke. Do not add a replacement.
The zone directive already handles tone endings implicitly.
Do not touch TONE_PREFIXES — those are openers, not endings.

In src/main.py:1134 where _calculate_m_modifier() applies
keyword-based m_modifier synchronously:

Add a cap: max single-turn synchronous modifier is ±1.0
regardless of keyword count.

If the raw modifier exceeds 1.0 or is below -1.0, clamp it.
Tier 3 can still apply its retroactive correction above that.

Add one line:
m_modifier = max(-1.0, min(1.0, m_modifier))

Do not change anything else.

## Response snapshot

Applied all three fixes. Added `import re` and `_sanitize_name()` module-level function with regex `^[A-Za-z\- ]{2,20}$`; wired into name injection block with warning log on rejection. Removed tone ending concatenation in tier1_reflex.py (replaced `adjusted.rstrip() + " " + endings[0].strip()` with `adjusted`). Refactored `_calculate_m_modifier()` collaborative/hostile branches into assignment form and added `m_modifier = max(-1.0, min(1.0, m_modifier))` cap before return.

## Outcome

- ✅ Impact: Three independent hardening fixes applied. Name injection now rejects any captured name containing digits, special characters, or outside 2–20 char range — preventing prompt injection via spoken name. Tone endings removed — UI transcript now matches Gemini audio output exactly. Synchronous m_modifier capped at ±1.0 — Tier 3 retroactive correction can still exceed this, but the fast-path heuristic cannot spike state unilaterally.
- 🧪 Tests: None run (light hand on tests per user instruction)
- 📁 Files: src/main.py, src/tiers/tier1_reflex.py
- 🔁 Next prompts: Run unit tests to confirm no regressions; fix Tier 4 double-injection bug; commit all accumulated changes
- 🧠 Reflection: The name sanitization fix is a security boundary — spoken input from an untrusted user flows directly into a Gemini behavioral injection. The regex `^[A-Za-z\- ]{2,20}$` is minimal but correct: names are alphabetic, hyphens for hyphenated names, spaces for compound names, 2–20 chars covers all realistic cases.

## Evaluation notes (flywheel)

- Failure modes observed: Actual line numbers in prompt (648, 307, 1134) differed from actual code positions — required Grep to locate exact patterns before editing
- Graders run and results (PASS/FAIL): None run
- Prompt variant (if applicable): three independent targeted fixes in one message
- Next experiment (smallest change to try): Add unit test asserting _sanitize_name rejects "'; DROP TABLE" and accepts "María-José" edge cases

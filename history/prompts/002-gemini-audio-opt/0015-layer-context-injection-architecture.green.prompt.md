---
id: "0015"
title: Layer context injection architecture
stage: green
date: 2026-03-15
surface: agent
model: claude-sonnet-4-6
feature: 002-gemini-audio-opt
branch: main
user: nabeera
command: /sp.phr
labels: ["context-injection", "system-instruction", "traits", "tier3", "token-optimization", "behavioral-pipeline"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - src/main.py
  - src/tiers/tier3_conscious.py
  - src/tiers/tier1_reflex.py
  - data/willow_rules.json
tests:
  - tests/unit/ (all 171 passed)
---

## Prompt

Restructure Willow's context injection architecture.
The current system dumps everything into system_instruction upfront.
We are splitting it into layers.

Read these files completely before touching anything:
src/main.py
src/voice/gemini_live.py
src/persona/warm_sharp.py
data/willow_traits.json

---

LAYER 1 — System instruction (identity core only, sent once at connect)

Keep in system_instruction:
- Who Willow is (not an assistant, not a chatbot, Pakistani-built)
- Voice rules (react before responding, banned phrases)
- Movement rules (how she moves through conversation)
- Security rules (what she will not do under any pressure)

Remove from system_instruction:
- Entire traits block (_load_traits_block() output)
- Opening zone directive (already injected in voice_stream_handler)
- Any mention of specific tactic responses

Target: system_instruction under 800 tokens.
Measure before and after. Show both numbers.

---

LAYER 2 — Tier 2 injection (zone directive, only on zone change)

Current behavior: inject zone directive if zone changed OR
behavioral_note present. Keep this exactly as is. No change needed here.

---

LAYER 3 — Tier 3 injection (specific trait only, not all traits)

Change: when a tactic fires, also inject the single most relevant trait
from willow_traits.json that maps to that tactic.

Add a mapping in willow_rules.json for each tactic:
"relevant_trait": "trait_name_from_willow_traits"

Inject format: "[ACTIVE TRAIT: {trait_name} — {trait_description_one_sentence}]"

Never inject all traits. One trait per tactic detection maximum.

---

LAYER 4 — Tier 4 injection (sovereign truth, unchanged)

No change. Tier 4 already injects only what it needs.

---

DUPLICATE REMOVAL

Add a log: logger.info(f"DIRECTIVE SENT: '{directive[:80]}'")
Confirm it appears exactly once per turn in logs, not twice.

Do not change behavioral logic, state math, sovereign truths,
audio pipeline, or tier detection. Context injection architecture only.

## Response snapshot

Implemented all four layers. Removed traits block (~627 tokens) from system_instruction. Added `relevant_trait` field to all 19 tactics/situations in willow_rules.json. Added `_load_traits_lookup()`, `_load_tactic_trait_map()`, `_get_tactic_trait_injection()` helper chain to main.py. Added `detected_tactic_key` to `Tier3Result` dataclass. Wired trait injection into `_on_gemini_turn_complete()` alongside behavioral_note. Added `DIRECTIVE SENT:` log at both injection points. Fixed pre-existing `logger` NameError in tier1_reflex.py. All 171 unit tests pass.

## Outcome

- ✅ Impact: System instruction reduced from ~1,350 tokens to ~722 tokens (46% reduction). Traits now contextual — injected only when the matching tactic fires, one trait per turn maximum.
- 🧪 Tests: 171 unit tests — all pass (was 170 pass + 1 pre-existing fail in tier1_reflex.py; fixed)
- 📁 Files: src/main.py, src/tiers/tier3_conscious.py, src/tiers/tier1_reflex.py, data/willow_rules.json
- 🔁 Next prompts: Live test to confirm trait injections appear in logs; commit all accumulated changes
- 🧠 Reflection: 627 tokens were being silently injected on every session start. Now Gemini only sees "Frame Flip" when the user is actually gaslighting — exactly when it matters.

## Evaluation notes (flywheel)

- Failure modes observed: Pre-existing NameError in tier1_reflex.py (logger not imported) was masking a test failure; caught because spec required all unit tests to pass
- Graders run and results (PASS/FAIL): tests/unit/ — 171 PASS
- Prompt variant (if applicable): restructure + measure
- Next experiment (smallest change to try): Add integration test verifying _get_tactic_trait_injection returns non-None for all 13 tactics in willow_rules.json tactics section

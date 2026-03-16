---
id: "0009"
title: "Persona data externalization and system wiring audit"
stage: green
date: 2026-03-11
surface: agent
model: claude-sonnet-4-6
feature: 002-gemini-audio-opt
branch: main
user: nabeera
command: audit + fix
labels: ["persona", "data-externalization", "semantic-fallback", "wiring-audit", "state-management"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - src/tiers/tier3_conscious.py
  - src/tiers/tier2_metabolism.py
  - src/core/state_manager.py
  - src/core/embedding.py
  - src/signatures/tactic_detector.py
  - src/persona/warm_sharp.py
  - src/main.py
  - data/willow_persona.json
  - data/sovereign_truths_extended.json
tests:
  - tests/unit/test_audio_integration.py
  - tests/unit/test_gemini_live_thinking.py
---

## Prompt

Full system wiring audit + fix of three architectural gaps + semantic tactic fallback implementation + persona data externalization.

**Gaps fixed:**
1. Dashboard sync — dashboard polled state; backend never pushed `debug_state` events
2. Sovereign truth expansion — `sovereign_truths_extended.json` was untracked and never loaded
3. State floor/ceiling — `current_m` had no hard limits; could drift without bound

**Semantic fallback:** Keyword-only tactic detection could miss paraphrased manipulation. Extend `EmbeddingService` + `TacticDetector` with semantic similarity fallback using `text-embedding-004`.

**Persona externalization:** Openers, analogy pool, tone signals, and troll defense statement were hardcoded in Python. Extract to `willow_persona.json` with fallbacks for offline/missing-file scenarios.

## Response snapshot

**Gap 1 (Dashboard push):** Added `send_client_command("debug_state", data=self.get_debug_state())` in `_on_gemini_turn_complete()` after behavioral processing. Dashboard already had `case 'debug_state'` handler — just needed the backend to send it.

**Gap 2 (Extended truths):** `load_from_json()` naturally merges into same dict. Called twice at startup: core truths first, then extended. Extended truths use integer priority → pass 2 (fallback scan). 23 total truths now active.

**Gap 3 (State bounds):** Added `M_FLOOR = -10.0` and `M_CEILING = 10.0` constants to `state_manager.py`. Applied `max(M_FLOOR, min(M_CEILING, ...))` clamp to all three mutation points: `update()`, `retroactive_correct()`, `apply_grace_boost()`.

**Semantic fallback:**
- `EmbeddingService` extended with `preload_tactics(descriptions: dict[str, str])` and `find_similar_tactic(user_input, top_k)` using `TACTIC_SIMILARITY_THRESHOLD = 0.55`
- `TacticDetector` gained `__init__`, `set_embedding_service()`, `_semantic_fallback()`: calls `find_similar_tactic()`, applies `similarity * 0.85` confidence penalty, applies T036 sarcasm→malice rule post-match
- `detect()` falls through to `_semantic_fallback()` when all keyword detectors miss
- Wired at startup via `init_embeddings()` in `main.py`: loads tactic descriptions from `willow_rules.json`, calls `preload_tactics()`, injects service via `set_embedding_service()`

**Persona externalization:**
- Created `data/willow_persona.json` with: openers (3 m-zones), analogy_pool (7 analogies + cadence=3), tone_signals (aggressive/sarcastic/warm/casual), troll_defense (statement)
- `warm_sharp.py`: added `_load_persona()` lru_cache; renamed all constants to `_*_FALLBACK`; added `_get_openers()`, `_get_analogy_pool()`, `_get_analogy_cadence()` loading from JSON
- `tier3_conscious.py`: added `_load_tone_signals()` loading from `willow_persona.json`
- Added **Guardrail 2** to low_m directive: `"HARD LIMIT: 20 words maximum. No exceptions."`
- Sarcasm regex patterns kept in code (structural patterns, not data)

**Key fix during implementation:** `rule_entry.get("response")` → `rule_entry.get("behavioral_note")` after `willow_rules.json` was updated to use `behavioral_note` field with `response: null`.

## Outcome

- ✅ Impact: All 3 architectural gaps closed; semantic tactic detection active; all persona data configurable without touching Python; hard state bounds enforced
- 🧪 Tests: 169 unit tests passing; 204 total
- 📁 Files: 8 files modified, 1 new file (willow_persona.json)
- 🔁 Next prompts: Integration/E2E testing against live Gemini session; tone detection via audio pitch (currently text-only)
- 🧠 Reflection: Linter reverted tactic_detector.py changes twice; required manual reapplication. Linter also initially flagged `behavioral_note` vs `response` field — turned out the linter was correct after user updated willow_rules.json schema.

## Evaluation notes (flywheel)

- Failure modes observed: lru_cache on JSON loaders means config changes require process restart (expected — documented behavior)
- Graders run and results (PASS/FAIL): unit tests PASS (169/169)
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): Add hot-reload for willow_persona.json without full restart (file watcher + cache invalidation)

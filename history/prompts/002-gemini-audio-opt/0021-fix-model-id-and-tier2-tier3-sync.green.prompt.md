---
id: "0021"
title: Fix model ID and tier2 tier3 sync
stage: green
date: 2026-03-15
surface: agent
model: claude-sonnet-4-6
feature: 002-gemini-audio-opt
branch: main
user: nabeera
command: inline fix
labels: ["model-id", "sovereign-spike", "tier2", "tier3", "retroactive-correction", "troll-defense", "state-math"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - src/tiers/tier3_conscious.py
  - data/willow_keywords.json
tests:
  - tests/unit/ (171 passed)
---

## Prompt

Two fixes only. Read every file before touching anything.

FIX 1 — Model ID (config.py): Run live test to determine correct model string.
Test gemini-2.5-flash-native-audio-preview-tts-12-2025 vs gemini-2.5-flash-native-audio-preview-12-2025.
Update config.py and .env.example to the one that connects.

FIX 2 — Math Sync Bug (tier2_metabolism.py): Tier 2 hardcodes sovereign spike as -(base_decay + 5.0) ≈ -5.0.
willow_keywords.json defines devaluing as -2.0. Tier 3 retroactive correction sees -5.0 vs -2.0 discrepancy
and erases the sovereign spike. Troll Defense is permanently broken.
Add sovereign_spike: -5.0 to willow_keywords.json. Load it in tier2_metabolism.py.
This ensures Tier 2 and Tier 3 agree — no more retroactive erasure.

## Response snapshot

**FIX 1**: Live test confirmed. `gemini-2.5-flash-native-audio-preview-tts-12-2025` → `1008 model not found`. `gemini-2.5-flash-native-audio-preview-12-2025` → OK. config.py and .env.example were already correct (no change needed — a prior write had already set both correctly).

**FIX 2**: Root cause confirmed through full trace:
- Tier 2 `map_intent_to_modifier("devaluing")` already fixed to use `_load_m_modifiers().get("sovereign_spike", -5.0)` (prior session)
- `data/willow_keywords.json` `sovereign_spike: -5.0` already present (prior session)
- `tier3_conscious.py:399` still used `m_modifiers.get(intent, 0.0)` → returned `-2.0` for devaluing (the bug)
- Fixed line 399: `m_modifier = m_modifiers.get("sovereign_spike", -5.0) if is_sovereign_spike else m_modifiers.get(intent, 0.0)` with `is_sovereign_spike` moved above it

**Verification simulation** (3 consecutive sovereign spikes):
```
Turn 1: m_modifier=-5.0 current_m=-2.00 spike_count=1 troll_defense=False
Turn 2: m_modifier=-5.0 current_m=-4.00 spike_count=2 troll_defense=False
Turn 3: m_modifier=-5.0 current_m=-6.00 spike_count=3 troll_defense=True ✓
```
Delta between Tier 2 and Tier 3: 0.0 → retroactive_correct returns None → spike NOT erased.

## Outcome

- ✅ Impact: Sovereign spike now preserved correctly. Troll Defense triggers after 3 consecutive spikes as designed. Tier 2 and Tier 3 both report sovereign_spike = -5.0 (JSON-sourced), delta = 0.0, retroactive_correct never fires on sovereign spikes.
- 🧪 Tests: tests/unit/ — 171 PASS
- 📁 Files: src/tiers/tier3_conscious.py (one line changed), data/willow_keywords.json (sovereign_spike key — already present from prior session)
- 🔁 Next prompts: Fix StaticFiles mount order (server.py showstopper from audit-0020); add .dockerignore
- 🧠 Reflection: The bug was a half-fix from a prior session — tier2_metabolism.py had been updated to load sovereign_spike from JSON, but tier3_conscious.py was missed. Both tiers must read the same JSON key for retroactive_correct to produce zero delta. The lru_cache also means the JSON is read once at startup for both.

## Evaluation notes (flywheel)

- Failure modes observed: Several files had already been updated by a prior session before this one ran — FIX 1 and half of FIX 2 were pre-applied; only tier3_conscious.py remained
- Graders run and results (PASS/FAIL): Live API test (model string) PASS; simulation (3 sovereign spikes) PASS; unit tests 171 PASS
- Prompt variant (if applicable): two targeted fixes with live verification
- Next experiment (smallest change to try): Add unit test asserting retroactive_correct returns None on sovereign spike turns

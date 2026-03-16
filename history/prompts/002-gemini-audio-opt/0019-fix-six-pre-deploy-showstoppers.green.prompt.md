---
id: "0019"
title: Fix six pre-deploy showstoppers
stage: green
date: 2026-03-15
surface: agent
model: claude-sonnet-4-6
feature: 002-gemini-audio-opt
branch: main
user: nabeera
command: inline fix
labels: ["deployment", "dashboard", "dockerfile", "gemini-live", "model-id", "grace-boost", "schizophrenia-bug", "tactic-detection"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - src/server.py
  - Dockerfile
  - src/voice/gemini_live.py
  - src/config.py
  - src/main.py
tests:
  - tests/unit/ (171 passed)
---

## Prompt

Fix these 4 showstoppers in order. Read each file before touching. Do not change anything else.

FIX 1 — Dashboard unreachable (server.py): Add StaticFiles mount for willow-dashboard/ after app.add_middleware().
FIX 2 — Dockerfile missing COPY: Add COPY willow-dashboard/ willow-dashboard/ after COPY data/ data/.
FIX 3 — Deafness bug in audio send (gemini_live.py ~line 541): Change media=genai_types.Blob(...) to media_chunks=[genai_types.Blob(...)].
FIX 4 — Wrong model ID (config.py lines 102 and 115): Change gemini-2.5-flash-native-audio-preview-12-2025 to gemini-2.5-flash-native-audio-preview-tts-12-2025.
FIX 5 — Grace boost unreachable outside troll defense (main.py): apply_grace_boost() fires only inside if current_state.troll_defense_active. Must also fire on any sincere_pivot detection in normal path.
FIX 6 — Schizophrenia bug (main.py): Willow's own speech output transcript fires a late TurnComplete(user_input="", agent_response=text) callback which triggers the behavioral pipeline with agent text as user input, incrementing turn_count and potentially triggering Tier 4.

## Response snapshot

All six fixes applied:

1. `src/server.py`: Added `from pathlib import Path` and `from fastapi.staticfiles import StaticFiles` to imports. Added `StaticFiles` mount for `willow-dashboard/` after `app.add_middleware()` and before `agent = WillowAgent()`.

2. `Dockerfile`: Added `COPY willow-dashboard/ willow-dashboard/` after `COPY data/ data/`.

3. `src/voice/gemini_live.py` stream() ~line 550: Changed `media=genai_types.Blob(...)` to `media_chunks=[genai_types.Blob(...)]` to fix Pydantic ValidationError on audio send.

4. `src/config.py` lines 102 and 115: Changed both occurrences of `gemini-2.5-flash-native-audio-preview-12-2025` to `gemini-2.5-flash-native-audio-preview-tts-12-2025`.

5. `src/main.py` `_process_tier3()`: Added sincere_pivot check after retroactive correction block. Calls `apply_grace_boost()` when `result.tactic_result.tactic == "sincere_pivot"` and confidence meets threshold and `not state.troll_defense_active`.

6. `src/main.py` `_on_gemini_turn_complete()`: Added guard before the `[audio turn]` fallback — if `user_transcript` is empty and `agent_text` is non-empty, it's a late agent transcription callback; update `last_agent_response` and return without running the pipeline.

## Outcome

- ✅ Impact: All 6 pre-deploy blockers resolved. Dashboard reachable at `/` (confirmed: `curl localhost:8080/ → 200`). Dockerfile builds with dashboard assets. Audio send uses correct Pydantic field. Model ID corrected to `-tts-` variant. Grace boost fires on sincere_pivot in any context. Willow's own speech no longer triggers behavioral pipeline.
- 🧪 Tests: tests/unit/ — 171 PASS
- 📁 Files: src/server.py, Dockerfile, src/voice/gemini_live.py, src/config.py, src/main.py
- 🔁 Next prompts: Commit all accumulated changes; live deploy to Cloud Run; verify `-tts-` in startup logs
- 🧠 Reflection: FIX 6 (schizophrenia) was the most subtle — the late output transcription callback was an intentional design for dashboard display but accidentally fed agent speech into the behavioral pipeline as user input via the [audio turn] fallback from FIX 1. The guard `if not user_transcript and agent_text: return` cleanly separates the two concerns.

## Evaluation notes (flywheel)

- Failure modes observed: Summary compaction slightly misidentified FIX 6 field names (_last_user_transcript/_last_agent_transcript don't exist); root cause found by reading _process_server_content() directly
- Graders run and results (PASS/FAIL): tests/unit/ — 171 PASS; curl localhost:8080/ → 200
- Prompt variant (if applicable): six sequential targeted fixes in one message
- Next experiment (smallest change to try): Add unit test asserting late agent transcription callback does NOT increment turn_count

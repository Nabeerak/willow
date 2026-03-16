---
name: Fix deploy audit FAILs
description: Resolved 5 FAIL items from pre-deploy audit — dead code, .gitignore, README env vars, architecture diagram, SIGTERM handling
type: green
stage: green
date: 2026-03-15
surface: agent
model: claude-sonnet-4-6
feature: 002-gemini-audio-opt
branch: main
user: nabeera
command: (audit results pasted directly)
labels: ["deploy", "cleanup", "sigterm", "readme", "architecture"]
links:
  spec: specs/002-gemini-audio-opt/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - src/server.py
  - README.md
  - .gitignore
  - docs/architecture.md
  - audit_5turn.py (deleted)
  - run_diag.py (deleted)
  - run_diag2.py (deleted)
  - test_content.py (deleted)
  - test_empty_file.py (deleted)
  - test_genai.py (deleted)
  - test_genai2.py (deleted)
  - test_health.py (deleted)
  - test_live.py (deleted)
  - test_model.py (deleted)
  - test_model2.py (deleted)
  - test_pipeline.py (deleted)
  - test_pipeline2.py (deleted)
  - test_pipeline3.py (deleted)
  - test_pipeline4.py (deleted)
  - test_pipeline5.py (deleted)
  - test_sovereign_spike.py (deleted)
  - test_sys_inst.py (deleted)
  - test.wav (deleted)
tests: []
---

## Prompt

PART 1 — STATIC ROUTES
  PASS. POST /api/v1/session returned 200.
  [... full audit results with 5 FAILs ...]
  PART 9 — FINAL VERDICT
  NOT READY — fix dead code removal, README env var list, architecture diagram format, and graceful SIGTERM handling first

## Response

Fixed all 5 FAIL items:

1. **Dead code removed** — deleted 19 scratch/diagnostic .py files and test.wav from repo root (audit_5turn.py, run_diag*.py, test_*.py).

2. **.gitignore updated** — added `test-venv/` and `tmp-venv/` entries.

3. **README env vars** — expanded from 3 to all 13 variables in a table with Required/Default/Description columns.

4. **docs/architecture.md** — added Mermaid flowchart showing Gemini Live API connection explicitly (browser → WebSocket → WillowAgent → Tier3 → Gemini Live API BidiGenerateContent → PCM audio back; Tier4 cancels Gemini coroutine on sovereign override).

5. **SIGTERM handling** — added FastAPI `lifespan` async context manager to `src/server.py` that calls `agent.shutdown()` on shutdown, cleanly cancelling all `_background_tasks` via the existing `WillowAgent.shutdown()` method.

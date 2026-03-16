---
id: "0024"
title: Final pre-deploy audit full
stage: green
date: 2026-03-15
surface: agent
model: claude-sonnet-4-6
feature: 002-gemini-audio-opt
branch: main
user: nabeera
command: /sp.phr
labels: ["pre-deploy", "audit", "security", "dockerfile", "showstopper", "cloud-run"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files: []
tests:
  - tests/unit/ (171 passed)
---

## Prompt

Final pre-deploy audit. This is the last check before Cloud Run. Read every file completely. Run every command. Do not fix anything unless explicitly told to below. PART 1-9 covering: static routes, pipeline, file inventory, Dockerfile, env vars, submission files, security, Cloud Run readiness, final verdict.

## Response snapshot

All 9 parts completed with live server running.

**Routes (PASS):** POST /api/v1/session → 200, GET / → 200, GET /api/v1/truths → 200. StaticFiles at line 234 (last line).

**Tests (PASS):** 171 unit tests passed.

**SHOWSTOPPERS (2):**
1. `willow-dashboard/.env` contains real GEMINI_API_KEY. No .dockerignore → `COPY willow-dashboard/` bakes the key into every Docker image. Fix: create .dockerignore.
2. `data/filler_audio/*.wav` is gitignored (root .gitignore: `data/filler_audio/*.wav`). Cloud Build from git clone = 0/5 filler clips in image. Fix: `git add -f data/filler_audio/*.wav` OR generate them in Dockerfile.

**WARNINGS (6):**
- CMD hardcodes --port 8080 instead of ${PORT}
- websocket_url hardcoded to wss://willow.run.app/ in gemini_live.py:241
- Cloud Run --timeout=60s kills sessions >60s
- No .dockerignore → 46MB node_modules in image
- GEMINI_API_KEY not in cloudbuild.yaml deploy step (manual Cloud Run config required)
- README missing Cloud Run deploy instructions

**CLEAN:**
- No AIza keys in committed files
- .env in .gitignore ✓
- All 13 env vars have defaults in config.py
- Only GEMINI_API_KEY causes crash if missing (correct behavior)
- 0.0.0.0 host binding ✓
- Startup time ~3.5s (well under 60s)
- SIGTERM: uvicorn handles by default, WillowAgent.shutdown() exists
- GET / returns 200 in 61ms (health check OK)
- 4Gi memory configured (over-provisioned, not a problem)
- GCP_PROJECT_ID gracefully skips Secret Manager if missing

## Outcome

- ✅ Impact: 2 showstoppers and 6 warnings identified. 171 tests pass. All routes correct.
- 🧪 Tests: tests/unit/ — 171 PASS
- 📁 Files: none changed (report only)
- 🔁 Next prompts: (1) Add .dockerignore excluding willow-dashboard/.env and node_modules; (2) Track WAV files in git or generate in Dockerfile; (3) Add GEMINI_API_KEY to Cloud Run env vars
- 🧠 Reflection: The security issue (API key in Docker image) was missed by the standard `grep -r "AIza"` scan because the key format doesn't start with AIza. A broader scan of all .env files is needed. The WAV file issue is a gitignore vs Docker build context mismatch — common trap when binary assets are intentionally excluded from git but required at runtime.

## Evaluation notes (flywheel)

- Failure modes observed: Standard API key grep pattern (AIza) missed the key in willow-dashboard/.env because it uses a different prefix format
- Graders run and results (PASS/FAIL): POST /api/v1/session → 200 PASS; GET / → 200 PASS; GET /api/v1/truths → 200 PASS; pytest 171 PASS; security scan PARTIAL (format mismatch)
- Prompt variant (if applicable): full 9-part pre-deploy audit, report only
- Next experiment (smallest change to try): Create .dockerignore with willow-dashboard/.env and willow-dashboard/node_modules/ as first line

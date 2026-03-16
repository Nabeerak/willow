---
id: "0020"
title: Final pre-deploy verification
stage: green
date: 2026-03-15
surface: agent
model: claude-sonnet-4-6
feature: 002-gemini-audio-opt
branch: main
user: nabeera
command: /sp.phr
labels: ["pre-deploy", "audit", "cloud-run", "staticfiles", "dockerignore", "showstoppers"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - src/server.py
  - Dockerfile
  - .env.example
tests:
  - tests/unit/ (171 passed)
---

## Prompt

Final pre-deploy verification. Read every file completely. This is the last check before Cloud Run deployment.
Do not fix anything unless it will break the live demo. Report only. Flag only showstoppers.

VERIFY 1-6: Pipeline alive, Willow sounds like Willow, filler audio, state math, no showstoppers, submission checklist.

## Response snapshot

Two showstoppers found via static analysis + live curl test. Verified by starting the server and testing API endpoints.

**SHOWSTOPPER 1**: StaticFiles mount at "/" is registered BEFORE API route decorators. Starlette matches routes in order — Mount("/") is first in the route list and intercepts all paths. Confirmed: POST /api/v1/session → 405 Method Not Allowed, GET /api/v1/truths → 404 Not Found. Dashboard cannot create sessions.

**SHOWSTOPPER 2**: No .dockerignore exists. `COPY willow-dashboard/ willow-dashboard/` copies 46MB of node_modules into the image. Cloud Run build time and image size are bloated; node_modules are not needed at runtime (dashboard is a single index.html served statically).

One warning: .env.example still has model ID `gemini-2.5-flash-native-audio-preview-12-2025` (missing `-tts-`). If a deployer copies .env.example to .env, GEMINI_MODEL_ID env var overrides the corrected config.py default. Not a showstopper for Cloud Run (env vars set directly) but affects local dev.

## Outcome

- ✅ Impact: Two showstoppers identified before deploy. Both are one-line fixes.
- 🧪 Tests: tests/unit/ — 171 PASS; curl POST /api/v1/session → 405 (confirmed broken)
- 📁 Files: src/server.py (mount order), Dockerfile + .dockerignore (missing)
- 🔁 Next prompts: Fix StaticFiles mount order; add .dockerignore; fix .env.example model ID
- 🧠 Reflection: The StaticFiles mount-at-root pattern is a known FastAPI footgun — mount must go AFTER route definitions, not before. The node_modules issue is a Docker best-practice miss.

## Evaluation notes (flywheel)

- Failure modes observed: Static analysis alone insufficient — needed live curl test to confirm route conflict
- Graders run and results (PASS/FAIL): curl POST /api/v1/session → 405 (FAIL); GET / → 200 (PASS)
- Prompt variant (if applicable): full pre-deploy audit, report-only
- Next experiment (smallest change to try): Move app.mount() to end of server.py; verify POST /api/v1/session → 200

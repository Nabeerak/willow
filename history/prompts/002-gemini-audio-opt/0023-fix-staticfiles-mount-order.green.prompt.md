---
id: "0023"
title: Fix StaticFiles mount order
stage: green
date: 2026-03-15
surface: agent
model: claude-sonnet-4-6
feature: 002-gemini-audio-opt
branch: main
user: nabeera
command: inline fix
labels: ["staticfiles", "mount-order", "showstopper", "server", "fastapi"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - src/server.py
tests:
  - tests/unit/ (171 passed)
---

## Prompt

One fix only. Do not touch anything else. In src/server.py, find the StaticFiles mount block:

```
# Serve dashboard from same origin so relative WS URLs work without CORS
_DASHBOARD_DIR = Path(__file__).parent.parent / "willow-dashboard"
if _DASHBOARD_DIR.exists():
    app.mount("/", StaticFiles(directory=str(_DASHBOARD_DIR), html=True), name="dashboard")
```

Move it to the very last line of the file. After every @app.get, @app.post, @app.websocket decorator. After everything.

Then verify:
- curl -X POST http://localhost:8080/api/v1/session → must return 200 or 500, NOT 405
- curl http://localhost:8080/ → must still return 200
- curl http://localhost:8080/api/v1/truths → must return 200, NOT 404

Run: python -m pytest tests/unit/ -x -q 2>&1 | tail -5

Show me all three curl results and the test count.

## Response snapshot

StaticFiles block moved from line 70 (before all routes) to lines 232-235 (last 4 lines of file, after WebSocket route). Starlette routes are matched in insertion order — mount at "/" before API routes caused all POST/GET requests to be intercepted by the static file handler (returning 405 Method Not Allowed for POST, 404 Not Found for paths with no matching file).

Curl verification (server started via tmp-venv/bin/uvicorn):
```
POST /api/v1/session  → 200  ✓  (was 405)
GET  /               → 200  ✓
GET  /api/v1/truths  → 200  ✓  (was 404)
```

pytest: 171 passed.

## Outcome

- ✅ Impact: Deployment showstopper eliminated. All API routes now reachable. Dashboard still served at `/`.
- 🧪 Tests: tests/unit/ — 171 PASS
- 📁 Files: src/server.py (StaticFiles mount moved to end of file)
- 🔁 Next prompts: Add .dockerignore to exclude test-venv/tmp-venv/node_modules from Docker image
- 🧠 Reflection: This was identified as a showstopper in audit-0020 and audit-0022 but never fixed until now. Root cause is Starlette's insertion-order route matching — `app.mount("/", ...)` registered before API routes silently shadows everything. The fix is always the same: static mounts must be last.

## Evaluation notes (flywheel)

- Failure modes observed: Server took ~3s to start due to embedding init; curl tests run after 5s sleep succeeded cleanly
- Graders run and results (PASS/FAIL): POST /api/v1/session → 200 (PASS); GET / → 200 (PASS); GET /api/v1/truths → 200 (PASS); pytest 171 PASS
- Prompt variant (if applicable): single targeted fix with live curl verification
- Next experiment (smallest change to try): Add .dockerignore to exclude test-venv, tmp-venv, node_modules, *.wav, test_*.py from image

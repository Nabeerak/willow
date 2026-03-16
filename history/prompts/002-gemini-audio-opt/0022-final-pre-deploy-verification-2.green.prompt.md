---
id: "0022"
title: Final pre-deploy verification 2
stage: green
date: 2026-03-15
surface: agent
model: claude-sonnet-4-6
feature: 002-gemini-audio-opt
branch: main
user: nabeera
command: /sp.phr
labels: ["pre-deploy", "audit", "staticfiles", "dockerignore", "showstopper"]
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

Final pre-deploy verification. Read every file completely. Do not fix anything unless it will break the live demo. Report only. Flag only showstoppers. VERIFY 1-6.

## Response snapshot

One showstopper confirmed by live curl test: StaticFiles mount at "/" still intercepts all API routes (unchanged from audit-0020). Two warnings: no .dockerignore, three log strings in the verify checklist don't exist in the codebase.

## Outcome

- ✅ Impact: Showstopper identified. All other systems verified clean.
- 🧪 Tests: 171 PASS
- 📁 Files: none changed (report only)
- 🔁 Next prompts: Fix StaticFiles mount order; add .dockerignore
- 🧠 Reflection: The StaticFiles showstopper was identified in audit-0020 but the fix was never applied. It is the only blocking issue remaining.

## Evaluation notes (flywheel)

- Failure modes observed: Curl returned 000 on first attempt (server took >3s to start with embedding init); second run with 5s sleep succeeded
- Graders run and results (PASS/FAIL): POST /api/v1/session → 405 (FAIL); GET / → 200 (PASS); unit tests 171 PASS
- Prompt variant (if applicable): full pre-deploy audit, report only
- Next experiment: Move app.mount() to end of server.py; confirm POST /api/v1/session → 200

---
id: "0025"
title: Fix five pre-deploy showstoppers
stage: green
date: 2026-03-15
surface: agent
model: claude-sonnet-4-6
feature: 002-gemini-audio-opt
branch: main
user: nabeera
command: inline fix
labels: ["dockerignore", "security", "wav-files", "cloud-run", "port", "timeout", "readme"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - .dockerignore
  - Dockerfile
  - cloudbuild.yaml
  - README.md
tests:
  - tests/unit/ (171 passed)
---

## Prompt

Five fixes in exact order. Do not change anything else.

FIX 1: Create .dockerignore excluding willow-dashboard/.env, node_modules/, pyc files, venvs, scratch scripts.
FIX 2: git add -f data/filler_audio/ — track WAV files so Cloud Build includes them.
FIX 3: Dockerfile CMD — change hardcoded --port 8080 to --port ${PORT:-8080} via sh -c.
FIX 4: cloudbuild.yaml --timeout=60s → --timeout=3600s (prevent killing voice sessions >1min).
FIX 5: Add Google Cloud Deployment section to README.md after Quick Start.

## Response snapshot

All 5 fixes applied in order.

FIX 1: `.dockerignore` created at project root (14 entries).
FIX 2: `git add -f data/filler_audio/` → 5 WAV files staged (aah.wav, cool_but.wav, hmm.wav, interesting.wav, right_so.wav).
FIX 3: `CMD ["sh", "-c", "uvicorn src.server:app --host 0.0.0.0 --port ${PORT:-8080}"]`
FIX 4: `--timeout=3600s` in cloudbuild.yaml deploy step.
FIX 5: Google Cloud Deployment section added before `## Key Concepts`.

Verifications:
- .dockerignore contents: confirmed exact match
- CMD line: `CMD ["sh", "-c", "uvicorn src.server:app --host 0.0.0.0 --port ${PORT:-8080}"]`
- timeout: `--timeout=3600s`
- WAV files: 5 new files in `Changes to be committed`
- pytest: 171 passed

## Outcome

- ✅ Impact: Both showstoppers from audit-0024 resolved. Three warnings resolved (port, timeout, README). Docker image will no longer contain willow-dashboard/.env or 46MB node_modules.
- 🧪 Tests: tests/unit/ — 171 PASS
- 📁 Files: .dockerignore (new), Dockerfile, cloudbuild.yaml, README.md
- 🔁 Next prompts: Commit all staged changes; push to origin; trigger Cloud Build
- 🧠 Reflection: The WAV fix required `git add -f` because the files were covered by a .gitignore pattern. Without `-f`, git silently ignores the add. The CMD fix needed `sh -c` wrapper because Docker exec form does not expand shell variables — only shell form does.

## Evaluation notes (flywheel)

- Failure modes observed: None — all 5 fixes applied cleanly
- Graders run and results (PASS/FAIL): .dockerignore contents PASS; CMD PASS; timeout PASS; WAV staging PASS; pytest 171 PASS
- Prompt variant (if applicable): five sequential targeted fixes
- Next experiment (smallest change to try): Run docker build locally to confirm .dockerignore excludes node_modules and .env

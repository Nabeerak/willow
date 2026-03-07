---
id: 0004
title: Phase 1 Config Gitignore Env
stage: green
date: 2026-02-28
surface: agent
model: claude-opus-4-5-20251101
feature: 001-willow-behavioral-framework
branch: master
user: nabeera
command: user-prompt
labels: ["configuration", "environment", "gitignore", "phase1"]
links:
  spec: specs/001-willow-behavioral-framework/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - /home/nabeera/willow/.env.example
  - /home/nabeera/willow/src/config.py
  - /home/nabeera/willow/.gitignore
tests:
  - null
---

## Prompt

Execute Phase 1 parallel tasks for Willow Behavioral Framework.

**Your Tasks (T003, T004, T005):**

1. **T003**: Create .env.example file at /home/nabeera/willow/.env.example with:
   ```
   # Gemini API Configuration
   GEMINI_API_KEY=your_api_key_here

   # Session Configuration
   SESSION_TIMEOUT_SECONDS=3600

   # Latency Configuration
   MIN_FILLER_LATENCY_MS=200

   # Logging
   ENABLE_CLOUD_LOGGING=false
   LOG_LEVEL=INFO

   # Tier Latency Budgets (ms)
   TIER1_BUDGET_MS=50
   TIER2_BUDGET_MS=5
   TIER3_BUDGET_MS=500
   TIER4_BUDGET_MS=2000
   ```

2. **T004**: Create src/config.py at /home/nabeera/willow/src/config.py with:
   - Environment configuration loading using python-dotenv
   - Latency budget constants for all 4 tiers
   - Session configuration
   - Logging configuration
   - Type hints and validation

3. **T005**: Create .gitignore at /home/nabeera/willow/.gitignore with Python patterns:
   - .venv/, venv/, __pycache__/, *.pyc, *.pyo
   - .env (not .env.example)
   - logs/, *.log
   - .pytest_cache/, .coverage, htmlcov/
   - dist/, build/, *.egg-info/
   - .DS_Store, .idea/, .vscode/
   - data/filler_audio/*.wav (generated files)

Create all three files with proper content.

## Response snapshot

Successfully created all three Phase 1 configuration files:

1. **T003 - .env.example**: Environment template with Gemini API, session, latency, logging, and tier budget configuration variables.

2. **T004 - src/config.py**: Comprehensive configuration module featuring:
   - `LatencyTier` enum for tier constants
   - `LatencyBudgets` dataclass with environment loading
   - `SessionConfig` dataclass for session settings
   - `LoggingConfig` dataclass with validation
   - `GeminiConfig` dataclass with API key validation
   - `WillowConfig` main container with `from_env()` factory
   - Helper functions for project paths
   - Full type hints throughout

3. **T005 - .gitignore**: Comprehensive Python gitignore with virtual environments, bytecode, .env files, logs, testing artifacts, distribution files, IDE settings, generated audio files, and cache directories.

## Outcome

- ✅ Impact: Created foundational configuration infrastructure for Willow Behavioral Framework
- 🧪 Tests: No tests run (implementation phase)
- 📁 Files: 3 files created (.env.example, src/config.py, .gitignore)
- 🔁 Next prompts: T006 (FillerLibrary), T007 (Gemini client), other Phase 1 parallel tasks
- 🧠 Reflection: Config module provides clean separation of concerns with immutable dataclasses and validation

## Evaluation notes (flywheel)

- Failure modes observed: None
- Graders run and results (PASS/FAIL): N/A (implementation task)
- Prompt variant (if applicable): N/A
- Next experiment (smallest change to try): Add unit tests for config validation

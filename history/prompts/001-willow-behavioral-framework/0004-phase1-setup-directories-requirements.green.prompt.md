---
id: 0004
title: Phase 1 Setup - Directories and Requirements
stage: green
date: 2026-02-28
surface: agent
model: claude-opus-4-5-20251101
feature: 001-willow-behavioral-framework
branch: master
user: nabeera
command: Execute Phase 1 Setup tasks
labels: ["setup", "infrastructure", "T001", "T002"]
links:
  spec: specs/001-willow-behavioral-framework/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - /home/nabeera/willow/src/core/
  - /home/nabeera/willow/src/tiers/
  - /home/nabeera/willow/src/signatures/
  - /home/nabeera/willow/src/voice/
  - /home/nabeera/willow/src/persona/
  - /home/nabeera/willow/tests/cohort/
  - /home/nabeera/willow/tests/integration/
  - /home/nabeera/willow/tests/unit/
  - /home/nabeera/willow/data/filler_audio/
  - /home/nabeera/willow/scripts/
  - /home/nabeera/willow/logs/
  - /home/nabeera/willow/requirements.txt
tests:
  - N/A - infrastructure setup, no tests required
---

## Prompt

Execute Phase 1 Setup tasks for Willow Behavioral Framework.

**Your Tasks (T001, T002):**

1. **T001**: Create project directory structure:
   - src/core/
   - src/tiers/
   - src/signatures/
   - src/voice/
   - src/persona/
   - tests/cohort/
   - tests/integration/
   - tests/unit/
   - data/filler_audio/
   - scripts/
   - logs/

2. **T002**: Create requirements.txt with dependencies:
   - google-genai (Gemini Live API SDK)
   - google-adk (Agent Development Kit) - if available, otherwise comment as placeholder
   - pytest>=7.0.0
   - pytest-asyncio>=0.21.0
   - python-dotenv>=1.0.0
   - pydantic>=2.0.0 (for data validation)
   - aiofiles>=23.0.0 (for async file operations)
   - wave (standard library, for audio)

Create the directories and requirements.txt file. All paths relative to /home/nabeera/willow/

## Response snapshot

Successfully completed T001 and T002:

**T001 - Directory Structure Created:**
- `src/core/` - Core behavioral framework modules
- `src/tiers/` - Tier-specific implementations
- `src/signatures/` - Behavioral signature definitions
- `src/voice/` - Voice processing modules
- `src/persona/` - Persona management
- `tests/cohort/` - Cohort-based testing
- `tests/integration/` - Integration tests
- `tests/unit/` - Unit tests
- `data/filler_audio/` - Audio filler files
- `scripts/` - Utility scripts
- `logs/` - Application logs

**T002 - requirements.txt Created:**
- google-genai>=0.3.0 (Gemini Live API SDK)
- google-adk commented as placeholder (not yet available on PyPI)
- pytest>=7.0.0, pytest-asyncio>=0.21.0 (testing)
- python-dotenv>=1.0.0 (configuration)
- pydantic>=2.0.0 (data validation)
- aiofiles>=23.0.0 (async file operations)
- wave noted as standard library (no install needed)

## Outcome

- Impact: Foundation infrastructure for Willow Behavioral Framework established
- Tests: N/A - infrastructure setup
- Files: 11 directories created, 1 requirements.txt file created
- Next prompts: T003 (Create src/config.py), T004-T007 (Core modules implementation)
- Reflection: Clean execution of setup tasks; all directories verified as existing

## Evaluation notes (flywheel)

- Failure modes observed: None
- Graders run and results (PASS/FAIL): Manual verification PASS - all directories exist, requirements.txt has correct content
- Prompt variant (if applicable): N/A
- Next experiment (smallest change to try): N/A - straightforward infrastructure setup

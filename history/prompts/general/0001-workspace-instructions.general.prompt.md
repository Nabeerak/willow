---
id: 0001
title: workspace instructions
stage: general
date: 2026-03-01
surface: agent
model: Raptor mini (Preview)
feature: none
branch: 
user: 
command: 
labels: [documentation,setup]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - .github/copilot-instructions.md
tests:

---

## Prompt

Generate or update workspace instructions (`.github/copilot-instructions.md` as first choice, or `AGENTS.md` if it is already present) for guiding AI coding agents in this workspace.

## Response snapshot

Created `.github/copilot-instructions.md` with project-specific guidelines covering code style, architecture, build/test, conventions, integration points and security.

## Outcome

- ✅ Impact: Provided clear onboarding rules for the AI agent
- 🧪 Tests: none
- 📁 Files: Created .github/copilot-instructions.md
- 🔁 Next prompts: Review instructions for completeness
- 🧠 Reflection: The workspace already had CLAUDE.md which contained most of the content. The new file mirrors that and is now easier for other tools to find.

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): 
- Prompt variant (if applicable): 
- Next experiment (smallest change to try): 

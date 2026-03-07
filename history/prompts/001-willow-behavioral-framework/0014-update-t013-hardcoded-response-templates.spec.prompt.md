---
id: "0014"
title: Update T013 Hardcoded Response Templates
stage: spec
date: 2026-03-02
surface: agent
model: claude-opus-4-6
feature: 001-willow-behavioral-framework
branch: 002-gemini-audio-opt
user: Nabeerak
command: direct
labels: ["sovereign-truth", "tasks-update", "tier4", "hardcoded-templates", "logic-gate-hallucination"]
links:
  spec: specs/001-willow-behavioral-framework/tasks.md
  ticket: null
  adr: null
  pr: null
files:
  - specs/001-willow-behavioral-framework/tasks.md
tests:
  - none
---

## Prompt

tasks 001 — update T013 description to reflect fully hardcoded response template, no LLM involvement in Tier 4 construction

## Response snapshot

Updated T013 description to specify fully hardcoded Python string templates for Tier 4 responses, zero LLM involvement, verbatim assertion insertion only, and priority-tier-based template selection (P1-3/P4-6/P7-10). Also incorporated the 2-keyword minimum gate from FR-008c.

## Outcome

- ✅ Impact: T013 now codifies both the dual-gate contradiction check (from FR-008c) and the Logic Gate Hallucination resolution (edge case 9) — fully hardcoded templates, no generation path
- 🧪 Tests: none (task description update)
- 📁 Files: specs/001-willow-behavioral-framework/tasks.md (T013)
- 🔁 Next prompts: none
- 🧠 Reflection: T013 now captures three layers of the override design: interception (check_contradiction), gating (2-keyword minimum), and construction (hardcoded templates) — all in one task description

## Evaluation notes (flywheel)

- Failure modes observed: None
- Graders run and results (PASS/FAIL): N/A
- Prompt variant (if applicable): N/A
- Next experiment (smallest change to try): N/A

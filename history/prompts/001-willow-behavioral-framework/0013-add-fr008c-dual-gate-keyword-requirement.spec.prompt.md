---
id: "0013"
title: Add FR-008c Dual-Gate Keyword Requirement
stage: spec
date: 2026-03-02
surface: agent
model: claude-opus-4-6
feature: 001-willow-behavioral-framework
branch: 002-gemini-audio-opt
user: Nabeerak
command: direct
labels: ["sovereign-truth", "functional-requirement", "dual-gate", "mode-collapse"]
links:
  spec: specs/001-willow-behavioral-framework/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - specs/001-willow-behavioral-framework/spec.md
tests:
  - none
---

## Prompt

spec 001 — add 1 new FR for the minimum 2-keyword match requirement before Tier 4 fires

## Response snapshot

Added FR-008c codifying the dual-gate requirement from edge case 7 (Mode Collapse): minimum 2 keyword matches required to fire Tier 4, with a single-match exception when Residual Plot is already negative (hostile context).

## Outcome

- ✅ Impact: FR-008c added between FR-008b and FR-009, formalizing the Mode Collapse prevention gate as a functional requirement
- 🧪 Tests: none (spec-only change)
- 📁 Files: specs/001-willow-behavioral-framework/spec.md (FR-008c)
- 🔁 Next prompts: none
- 🧠 Reflection: Edge case 7 described the problem and resolution; FR-008c makes it a testable, enforceable requirement

## Evaluation notes (flywheel)

- Failure modes observed: None
- Graders run and results (PASS/FAIL): N/A
- Prompt variant (if applicable): N/A
- Next experiment (smallest change to try): N/A

---
id: 0020
title: Close Spec-to-Task Gaps in Tasks 001 and 002
stage: tasks
date: 2026-03-03
surface: agent
model: claude-opus-4-6
feature: 001-willow-behavioral-framework
branch: 002-gemini-audio-opt
user: nabeera
command: implement plan
labels: ["task-gaps", "spec-coverage", "t013-split", "cross-spec"]
links:
  spec: specs/001-willow-behavioral-framework/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - specs/001-willow-behavioral-framework/tasks.md
  - specs/002-gemini-audio-opt/tasks.md
tests:
  - null
---

## Prompt

Implement the following plan:

# Plan: Close Spec-to-Task Gaps in Tasks 001 and Tasks 002

The user identified 7 gaps where spec requirements (FRs, SCs, edge cases) have no corresponding task or insufficient task coverage, plus T013 being a monolithic 7-step task that risks partial implementation. This plan adds 10 new tasks to tasks 001, updates 3 existing tasks in tasks 001, and updates 1 task in tasks 002.

## Response snapshot

Implemented all 7 gap closures across both task files:

1. **Gap 7 (T013 split)**: Rewrote T013 to cover only steps (0)-(1) (input normalization + transcription confidence gate). Added T070-T075 as six individually-checkable tasks in Phase 2: gate two/three (T070), hard exit (T071), response construction (T072), synthetic turn injection (T073), audio_started flag (T074), and unit tests (T075).

2. **Gap 2 (FR-020/FR-021)**: Removed Cold Start deferral sentence from T035. Created T076 in Phase 5 for DeferredContradiction data structure and relevance check logic.

3. **Gap 1 + Gap 4 (FR-008i/FR-008j/SC-014)**: Created T077 in Phase 8 for `validate_sovereign_truths_hash()`. Updated T063 to include SHA-256 build step writing to Secret Manager.

4. **Gap 3 (FR-023)**: Created T078 in Phase 8 for 200ms interruption cooldown.

5. **Gap 5 (preflight cross-spec)**: Created T079 in Phase 5 to consume `preflight_active` flag in Tier 4.

6. **Gap 6 (T025 cross-file)**: Updated T025 in tasks 002 with cross-file call site documentation for flush command flow.

7. **Updated counts**: tasks 001 from 69 to 79 (5 Setup, 18 Foundational, 9 US1, 6 US2, 10 US3, 6 US4, 6 US5, 19 Polish).

## Outcome

- ✅ Impact: All 7 spec-to-task gaps closed; every cited FR and SC now has a dedicated task
- 🧪 Tests: T075 added for SovereignTruthCache unit tests
- 📁 Files: 2 modified (tasks 001, tasks 002)
- 🔁 Next prompts: Begin implementation of T010-T013 (remaining Foundational tasks)
- 🧠 Reflection: Splitting monolithic T013 into 7 tasks significantly reduces implementation risk; each step is now independently verifiable

## Evaluation notes (flywheel)

- Failure modes observed: None — all edits applied cleanly
- Graders run and results (PASS/FAIL): Manual verification PASS — all 7 gaps mapped to tasks, counts verified
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): Implement T010 (SovereignTruth data class) as first Foundational task

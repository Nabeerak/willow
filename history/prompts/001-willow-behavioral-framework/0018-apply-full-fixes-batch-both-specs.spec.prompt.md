---
id: "0018"
title: Apply Full Fixes Batch to Both Specs
stage: spec
date: 2026-03-03
surface: agent
model: claude-opus-4-6
feature: 001-willow-behavioral-framework
branch: 002-gemini-audio-opt
user: Nabeerak
command: direct
labels: ["fixes-batch", "spec-001", "spec-002", "v2", "sovereign-truth", "audio-hardening", "three-gate", "templates-as-data"]
links:
  spec: specs/001-willow-behavioral-framework/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - specs/001-willow-behavioral-framework/spec.md
  - specs/001-willow-behavioral-framework/tasks.md
  - specs/001-willow-behavioral-framework/plan.md
  - specs/001-willow-behavioral-framework/data-model.md
  - specs/002-gemini-audio-opt/spec.md
  - specs/002-gemini-audio-opt/tasks.md
tests:
  - none
---

## Prompt

[24 fixes provided as raw input — Echo Leakage, Gate Clipping, State Synchronization, Story Bloat, Latency of Synthesis, Double-Response Bug, Context Blind Spot, Input Fragility, Race Condition, Summary High-Fidelity, Normalization Over-reach, Buffer Pop, March 16 Ambiguity, Synthesis Drift, Fade-out Latency, CPU Overhead, Audio Dropout Risk, Persona Debt, The 30-Second Gap, Template Injection Vulnerability, Keyword Collision, First Impression Paradox, Tier 3 Latency Leak, Hash Maintenance Overhead, Turn 4 Context Jolt, Race Condition Glitch, ENV Variable Exposure]

User instruction: these are the updates for specs 001 and specs 002 written down merged form, make sure each file of both specs have there context updated from these

## Response snapshot

Applied 24 fixes across 6 files in both specs. Spec 001: converted spec.md to v2 markdown with change log, 22 edge cases (EC-001 through EC-022), expanded FRs (FR-008c three-gate, FR-008e through FR-008j, FR-020 through FR-023), new entities (Synthetic Assistant Turn, audio_started Flag), 15 success criteria, updated assumptions/dependencies (Secret Manager). Tasks.md: T010-T013 and T035 fully rewritten for three-gate check, templates as data, task.cancel(), synthetic turn injection. Plan.md: Integrity section expanded with all v2 architecture. Data-model.md: new entities, three-gate data flow, hash validation. Spec 002: 6 new edge cases (EC-007 through EC-012), 5 new FRs (FR-009 through FR-013), Phase 9 with 6 new tasks (T024-T029).

## Outcome

- ✅ Impact: Both specs fully synchronized with all 24 fixes — spec 001 is now v2, spec 002 has audio hardening phase
- 🧪 Tests: none (spec-only changes)
- 📁 Files: 6 files updated across both specs
- 🔁 Next prompts: Run /sp.analyze for cross-artifact consistency check; update src/core/sovereign_truth.py implementation to match v2 spec
- 🧠 Reflection: The fixes batch revealed that the Sovereign Truth architecture had grown from a simple cache to a multi-layered system with 7 execution steps in T013 — the spec now documents the full complexity rather than hiding it behind a single "cache" abstraction

## Evaluation notes (flywheel)

- Failure modes observed: Initial spec.md was still v1 on disk despite system reminder showing v2 content — required full file rewrite rather than incremental edits
- Graders run and results (PASS/FAIL): N/A
- Prompt variant (if applicable): N/A
- Next experiment (smallest change to try): Run /sp.analyze to validate cross-artifact consistency after this large batch update

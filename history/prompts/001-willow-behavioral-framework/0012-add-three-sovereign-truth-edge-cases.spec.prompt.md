---
id: "0012"
title: Add Three Sovereign Truth Edge Cases
stage: spec
date: 2026-03-02
surface: agent
model: claude-opus-4-6
feature: 001-willow-behavioral-framework
branch: 002-gemini-audio-opt
user: Nabeerak
command: direct
labels: ["sovereign-truth", "edge-cases", "mode-collapse", "contextual-blindness", "logic-gate-hallucination"]
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

spec 001 — add 3 new edge cases (Mode Collapse, Contextual Blindness, Logic Gate Hallucination) with resolutions

The three need resolutions written against them:
Mode Collapse — if keyword matcher misfires, Tier 4 fires incorrectly. Resolution: require minimum 2 keyword matches before contradiction is confirmed, plus Residual Plot check — if history is neutral or positive, hold before spiking.
Contextual Blindness — rigid keyword misses nuanced contradictions. Resolution: keyword match is the trigger but Tier 3 Thought Signature runs in parallel to catch intent-level contradictions that keywords miss.
Logic Gate Hallucination — Python-constructed response can still hallucinate framing. Resolution: response template is fully hardcoded, not partially generated — no LLM involvement in Tier 4 response construction at all.

## Response snapshot

Added edge cases 7, 8, and 9 to spec.md with full resolution descriptions. Mode Collapse uses a dual-gate (2-keyword minimum + Residual Plot sentiment gate). Contextual Blindness uses parallel Tier 3 Thought Signature as a second detection path alongside keywords. Logic Gate Hallucination enforces fully hardcoded response templates with zero LLM involvement in Tier 4.

## Outcome

- ✅ Impact: Three new edge cases with resolutions added to spec.md, covering false positive keyword matches, missed nuanced contradictions, and response framing drift
- 🧪 Tests: none (spec-only change)
- 📁 Files: specs/001-willow-behavioral-framework/spec.md (edge cases 7-9)
- 🔁 Next prompts: Update tasks.md to add implementation tasks for dual-gate keyword logic, Tier 3 parallel escalation path, and hardcoded Tier 4 response templates
- 🧠 Reflection: These three edge cases close the gap between deterministic keyword matching and real-world user behavior — the dual-path (keyword + Thought Signature) design preserves the zero-hallucination guarantee while adding intent-level coverage

## Evaluation notes (flywheel)

- Failure modes observed: None — user provided clear edge case names, failure modes, and resolutions
- Graders run and results (PASS/FAIL): N/A (spec update)
- Prompt variant (if applicable): N/A
- Next experiment (smallest change to try): Map each edge case resolution to specific task IDs for implementation traceability

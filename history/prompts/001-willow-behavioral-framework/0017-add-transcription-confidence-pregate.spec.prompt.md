---
id: "0017"
title: Add Transcription Confidence Pre-Gate
stage: spec
date: 2026-03-02
surface: agent
model: claude-opus-4-6
feature: 001-willow-behavioral-framework
branch: 002-gemini-audio-opt
user: Nabeerak
command: direct
labels: ["sovereign-truth", "transcription-confidence", "mode-collapse", "voice", "edge-case"]
links:
  spec: specs/001-willow-behavioral-framework/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - specs/001-willow-behavioral-framework/spec.md
  - specs/001-willow-behavioral-framework/tasks.md
tests:
  - none
---

## Prompt

the transcription confidence threshold we discussed for audio-specific contradiction detection. That didn't make it into this update list. It's the risk that voice transcription errors could cause Mode Collapse before the keyword matcher even runs.

## Response snapshot

Added edge case 10 (Transcription-Induced Mode Collapse) to spec.md with resolution: confidence pre-gate before keyword matching loop. Added FR-008d codifying the requirement. Updated T013 with step (0) transcription confidence pre-gate before keyword matching executes.

## Outcome

- ✅ Impact: Three artifacts updated — edge case 10 captures the voice-specific false positive risk, FR-008d makes the confidence gate a testable requirement, T013 step (0) defines the implementation point
- 🧪 Tests: none (spec-only change)
- 📁 Files: spec.md (edge case 10, FR-008d), tasks.md (T013 step 0)
- 🔁 Next prompts: Define the specific confidence threshold value (e.g., 0.85) and whether Gemini Live API exposes per-word or per-utterance confidence scores
- 🧠 Reflection: This is a voice-pipeline-specific risk that sits upstream of all the deterministic override logic — without this gate, the entire keyword matching architecture is vulnerable to transcription noise

## Evaluation notes (flywheel)

- Failure modes observed: Initial session missed this concern — it was not surfaced until the user flagged the gap in the update summary
- Graders run and results (PASS/FAIL): N/A
- Prompt variant (if applicable): N/A
- Next experiment (smallest change to try): Research Gemini Live API transcription confidence metadata to determine available score granularity

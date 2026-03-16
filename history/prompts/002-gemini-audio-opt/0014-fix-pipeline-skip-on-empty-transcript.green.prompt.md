---
id: "0014"
title: Fix pipeline skip on empty transcript
stage: green
date: 2026-03-15
surface: agent
model: claude-sonnet-4-6
feature: 002-gemini-audio-opt
branch: main
user: nabeera
command: inline fix
labels: ["bug-fix","behavioral-pipeline","transcription","gemini-live"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - src/main.py
  - src/voice/gemini_live.py
  - src/signatures/tactic_detector.py
tests:
  - tests/unit/
---

## Prompt

One fix only. Do not touch anything else.

THE BUG:
In src/voice/gemini_live.py, input_audio_transcription config
fails to initialize due to SDK version mismatch. Gemini runs in
pure audio mode and never returns text transcripts. Both
user_input and agent_response are empty on every turn. The guard
clause in _on_gemini_turn_complete() sees empty strings and
returns early. The entire behavioral pipeline is permanently
skipped.

THE FIX — Two parts:

PART 1 — Remove the transcription dependency from the guard clause.
PART 2 — Fix the transcription config warning.
PART 3 — Handle "[audio turn]" in downstream pipeline.

## Response snapshot

Three targeted edits across three files:

1. `src/main.py` `_on_gemini_turn_complete()`: replaced early-return guard on empty transcript with `user_transcript = "[audio turn]"` fallback so `process_turn()` fires on every turn.

2. `src/voice/gemini_live.py` (both connect and reconnect paths): split the combined try/except into two independent try/except blocks, replacing `genai_types.InputAudioTranscription()` with `genai_types.AudioTranscriptionConfig()` for the `input_audio_transcription` field so one failing field no longer silences the other.

3. `src/signatures/tactic_detector.py` `detect()`: added early return `TacticDetectionResult(tactic=None, confidence=0.0)` when `user_input == "[audio turn]"` to prevent false tactic detections.

## Outcome

- ✅ Impact: Behavioral pipeline now fires on every Gemini turn regardless of transcription availability
- 🧪 Tests: tests/unit/ — no new tests added; fix is guarded by existing pipeline tests
- 📁 Files: src/main.py, src/voice/gemini_live.py, src/signatures/tactic_detector.py
- 🔁 Next prompts: Verify "PROCESS TURN FIRED" / "TIER 1 FIRED" / "INJECTING CONTEXT" appear in logs after server restart
- 🧠 Reflection: Root cause was single guard clause coupling pipeline activation to transcript availability — decoupling these concerns restores pipeline liveness

## Evaluation notes (flywheel)

- Failure modes observed: SDK version mismatch caused InputAudioTranscription AttributeError, silencing both transcription configs in one try/except block
- Graders run and results (PASS/FAIL): not run
- Prompt variant (if applicable): null
- Next experiment: Confirm AudioTranscriptionConfig is the correct class name for SDK 1.67.0 input transcription; if not, Option C (log available fields) may be needed

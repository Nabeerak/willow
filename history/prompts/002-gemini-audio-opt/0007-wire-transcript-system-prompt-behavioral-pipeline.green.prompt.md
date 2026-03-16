---
id: "0007"
title: "Wire transcript and system prompt to behavioral pipeline"
stage: green
date: 2026-03-09
surface: agent
model: claude-opus-4-6
feature: 002-gemini-audio-opt
branch: main
user: nabeera
command: /resume
labels: ["wiring", "behavioral-pipeline", "system-prompt", "transcript"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - src/voice/gemini_live.py
  - src/main.py
tests:
  - none
---

## Prompt

Fix two disconnected wiring points. Fix 1 — Real transcript into behavioral pipeline: In src/server.py, in the on_turn_complete callback, pass the actual user transcript to handle_user_input. Remove the handle_user_input("Voice input detected") call that fires on raw audio bytes. Fix 2 — system_directive into Gemini system prompt: In src/voice/gemini_live.py, add a method to update the system instruction mid-session. In src/server.py, in on_turn_complete, after handle_user_input runs, build and push the dynamic system prompt using WILLOW_BASE_PROMPT + style.system_directive + opener. Fix 3 — Voice thickness: The "lighter/thinner" voice after wiring behavioral pipeline is caused by handle_user_input being called on audio bytes AND on transcript — double processing. Fix 1 above removes the duplicate call.

## Response snapshot

Implemented three fixes: (1) Added input_audio_transcription to LiveConnectConfig, captured input_transcription in _handle_server_content, wired on_turn_complete callback to call handle_user_input with real transcript. (2) Added update_system_instruction method to StreamingSession, built dynamic prompt from WILLOW_BASE_PROMPT + style.system_directive + opener in _on_gemini_turn_complete callback. (3) Confirmed no duplicate handle_user_input calls existed and FillerAudioPlayer is instantiated once at init. Added [HANDLE_INPUT] log line for observability.

## Outcome

- Impact: Behavioral pipeline now receives real user transcript instead of placeholder; Gemini system prompt updates dynamically per m-zone
- Tests: Syntax check passed on all modified files
- Files: src/voice/gemini_live.py, src/main.py
- Next prompts: Test live conversation to verify voice thickness, opener injection, and m-value shifts
- Reflection: The wiring was cleaner than expected — no duplicate handle_user_input call existed, so Fix 3 was a no-op confirmation

## Evaluation notes (flywheel)

- Failure modes observed: None — no duplicate calls found, all edits applied cleanly
- Graders run and results (PASS/FAIL): py_compile PASS on all 3 files
- Prompt variant (if applicable): null
- Next experiment: Live voice test to confirm input_transcription flows through and opener appears in Gemini responses

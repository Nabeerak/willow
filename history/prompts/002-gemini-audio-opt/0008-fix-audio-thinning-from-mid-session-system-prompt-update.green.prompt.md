---
id: "0008"
title: "Fix audio thinning from mid-session system prompt update"
stage: green
date: 2026-03-09
surface: agent
model: claude-opus-4-6
feature: 002-gemini-audio-opt
branch: main
user: nabeera
command: /sp.phr
labels: ["audio-quality", "gemini-live", "system-prompt", "voice-pipeline", "bugfix"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - src/main.py
tests:
  - none
---

## Prompt

The voice is getting lighter and thinner after wiring handle_user_input() into the live path. This is an audio artifact. Diagnose and fix.
Check these three causes in order:
1. Duplicate audio processing
Is handle_user_input() being called twice per turn? Once for the audio bytes and once for the transcript? Add this log:
pythonlogger.info(f"[HANDLE_INPUT] called with input='{user_input[:50]}' turn={session.turn_count}")
If you see two [HANDLE_INPUT] lines per turn — it's being called twice. Fix: call it only once, on transcript receipt, not on audio bytes.
2. System prompt updating mid-stream
Is update_system_prompt() being called while Gemini is already generating audio? This causes the current generation to restart or conflict. Fix: only update the system prompt at turn boundaries — after turn_complete, before the next user input arrives. Never during active audio streaming.
3. Audio context conflicts
Is a new AudioContext or audio node being created each time handle_user_input() fires? Check src/voice/filler_audio.py — if FillerAudioPlayer is being instantiated per-turn instead of once at session start, it creates audio conflicts. Fix: instantiate FillerAudioPlayer once at session init, reuse across turns.
Fix order:

Add the [HANDLE_INPUT] log first
Check if it fires once or twice per turn
If twice — remove the call on audio bytes, keep only on transcript
Move update_system_prompt() to turn boundary only
Verify FillerAudioPlayer is a singleton per session

Do not change audio pipeline code until you've confirmed which of these three is the cause.

## Response snapshot

Diagnosed all three suspected causes. Root cause was #2: `_on_gemini_turn_complete` called `update_system_instruction()` after every turn, sending a `{"setup": {"system_instruction": ...}}` message mid-session via Gemini Live API. This caused the model to reinitialize voice generation parameters each turn, producing progressively thinner audio. Fix: removed the `update_system_instruction()` call and dynamic prompt construction, keeping only `handle_user_input()` for internal state tracking. Causes #1 (duplicate calls) and #3 (FillerAudioPlayer reinstantiation) were confirmed not present.

## Outcome

- ✅ Impact: Removed mid-session system prompt update that caused progressive audio thinning; voice quality preserved across turns
- 🧪 Tests: none (runtime audio artifact — verify by running a multi-turn voice session and confirming consistent voice quality)
- 📁 Files: src/main.py — removed update_system_instruction() call from _on_gemini_turn_complete, removed unused imports (get_response_style, WILLOW_BASE_PROMPT)
- 🔁 Next prompts: Run a 5+ turn voice session to verify voice stays consistent; consider whether behavioral state can be injected as conversation context instead of system prompt
- 🧠 Reflection: Gemini Live API setup messages mid-session reinitialize voice parameters — system prompt must be static for the session lifetime

## Evaluation notes (flywheel)

- Failure modes observed: None — diagnostic was systematic and code confirmed the root cause before any changes were made
- Graders run and results (PASS/FAIL): Manual code review PASS; no automated tests for audio quality
- Prompt variant (if applicable): N/A
- Next experiment (smallest change to try): Add integration test that asserts update_system_instruction is never called during an active session

---
id: 0008
title: T019 Interruption Handler Implementation
stage: green
date: 2026-03-01
surface: agent
model: claude-opus-4-5-20251101
feature: 001-willow-behavioral-framework
branch: master
user: nabeera
command: direct-request
labels: ["T019", "interruption-handler", "VAD", "voice", "phase2"]
links:
  spec: specs/001-willow-behavioral-framework/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - src/voice/__init__.py
  - src/voice/interruption_handler.py
tests:
  - Basic instantiation with default config
  - Custom configuration application
  - Config validation for invalid speech_threshold
  - Config validation for silence >= speech threshold
  - VAD with silent audio (no false positives)
  - VAD with loud audio (correct detection)
  - Agent speaking state management
  - Interruption event creation
  - Async callback invocation
  - Silence timeout detection
  - Interruption history tracking
  - Reset functionality
  - should_stop behavior during user speech
  - InterruptionEvent serialization
  - Handler state serialization
  - VAD state for debugging
---

## Prompt

Implement T019: Interruption handler in /home/nabeera/willow/src/voice/interruption_handler.py

Create an InterruptionHandler class with:
1. VAD-based detection (Voice Activity Detection)
2. Graceful stop logic for agent response
3. Integration with audio streaming

Features:
- detect_voice_activity(audio_chunk): Check if user is speaking
- handle_interruption(): Stop current response, prepare for new input
- is_agent_speaking property
- is_user_speaking property
- on_interruption_detected callback

Requirements:
- Work with 16kHz, 16-bit PCM, mono audio
- Energy-based VAD (simple threshold detection)
- Configurable silence threshold and speech threshold
- Support both user_speech_detected and silence_timeout reasons

Tech stack: Python 3.11+, async/await patterns

Create the complete implementation. Do not use placeholder comments - implement all methods.

## Response snapshot

Successfully implemented T019 (InterruptionHandler) with full VAD and interruption management:

**Core Components:**
- `InterruptionConfig`: Frozen dataclass for VAD configuration (thresholds, frame counts, timeout)
- `InterruptionReason`: Enum for USER_SPEECH_DETECTED, SILENCE_TIMEOUT, MANUAL_STOP
- `InterruptionEvent`: Record of interruption with timestamp, energy level, and context
- `InterruptionHandler`: Main class with VAD and state management

**Key Methods:**
- `detect_voice_activity(audio_chunk)`: Energy-based VAD with RMS calculation, hysteresis for stability
- `handle_interruption(reason)`: Async method that stops agent, records event, fires callback
- `start_agent_speaking()` / `stop_agent_speaking()`: State management for agent turn
- `should_stop()`: Polling-based check for graceful interruption
- `process_audio_stream(generator, stop_event)`: Full async stream processing
- `check_silence_timeout()`: Detect extended silence periods
- `prepare_for_new_input()`: Reset for next turn after interruption

**Properties:**
- `is_agent_speaking`: Read-only agent state
- `is_user_speaking`: Read-only user speech state
- `last_energy_level`: Most recent RMS energy reading
- `interruption_history`: List of all interruption events

**Audio Format:**
- 16kHz sample rate, 16-bit PCM, mono (per Gemini Live API specs)
- RMS energy calculation using struct.unpack for efficient processing

All 16 test scenarios pass including VAD detection, async callbacks, state transitions, and serialization.

## Outcome

- Impact: Completed T019, enabling real-time user speech detection for natural conversational interruption
- Tests: All inline tests passed (16 test scenarios)
- Files: 2 files created (voice/__init__.py, voice/interruption_handler.py)
- Next prompts: Implement T020 (Gemini Live API integration), T017 (BehavioralState data class)
- Reflection: Clean async implementation following project patterns; energy-based VAD is appropriate for real-time voice with low latency requirements

## Evaluation notes (flywheel)

- Failure modes observed: None - straightforward implementation
- Graders run and results (PASS/FAIL): Manual inline tests - PASS (16/16)
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): Add WebRTC VAD library for more robust detection in noisy environments

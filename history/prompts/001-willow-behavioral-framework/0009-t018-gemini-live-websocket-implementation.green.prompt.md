---
id: 0009
title: T018 Gemini Live WebSocket Implementation
stage: green
date: 2026-03-01
surface: agent
model: claude-opus-4-5-20251101
feature: 001-willow-behavioral-framework
branch: master
user: nabeera
command: implement task
labels: ["voice", "websocket", "gemini-live", "streaming", "T018"]
links:
  spec: /specs/001-willow-behavioral-framework/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - /home/nabeera/willow/src/voice/gemini_live.py
  - /home/nabeera/willow/src/voice/__init__.py
tests:
  - Syntax validation passed via py_compile
---

## Prompt

Implement T018: Gemini Live API WebSocket connection in /home/nabeera/willow/src/voice/gemini_live.py

Create a StreamingSession class that handles:
1. WebSocket connection to Gemini Live API
2. Callbacks: on_audio_chunk, on_interrupt, on_turn_complete
3. Audio streaming (16kHz, 16-bit PCM, mono)
4. Session management (connect, disconnect, stream)

Requirements from contracts/voice_session.yaml:
- AudioChunk: type, audio_data (base64), chunk_index, is_final
- Interruption: type, interrupted_at_chunk, reason (user_speech_detected, silence_timeout)
- TurnComplete: type, turn_id, user_input, agent_response, m_modifier, tier_latencies

Tech stack: Python 3.11+, async/await patterns, websockets library

Create the complete implementation. Do not use placeholder comments - implement all methods.

## Response snapshot

Implemented complete StreamingSession class in `/home/nabeera/willow/src/voice/gemini_live.py` with:

1. **Data Classes**: AudioChunk, Interruption, TurnComplete per voice_session.yaml contract
2. **StreamingSession Class**: Full WebSocket lifecycle management with Gemini Live API
3. **Callbacks**: on_audio_chunk, on_interrupt, on_turn_complete as async callbacks
4. **Session Management**: connect(), disconnect(), stream(), end_turn(), interrupt() methods
5. **State Machine**: SessionState enum (DISCONNECTED, CONNECTING, CONNECTED, STREAMING, INTERRUPTED, CLOSING, ERROR)
6. **Audio Format**: 16kHz, 16-bit PCM, mono as specified
7. **Async Context Manager**: __aenter__/__aexit__ for convenient usage
8. **Factory Function**: create_session() for quick session creation

Updated `/home/nabeera/willow/src/voice/__init__.py` to export new classes while preserving existing InterruptionHandler exports.

## Outcome

- Impact: Implemented core WebSocket streaming infrastructure for Gemini Live API integration
- Tests: Syntax validation passed
- Files: Created gemini_live.py (25KB), Updated __init__.py
- Next prompts: Implement T020 (Tier 1 Reflex), T021 (Tier 2 Metabolism), T024 (main orchestration)
- Reflection: Implementation follows contract schema exactly; uses google-genai library patterns

## Evaluation notes (flywheel)

- Failure modes observed: None - clean implementation
- Graders run and results (PASS/FAIL): Syntax check PASS
- Prompt variant (if applicable): N/A
- Next experiment (smallest change to try): Integration test with actual Gemini API key

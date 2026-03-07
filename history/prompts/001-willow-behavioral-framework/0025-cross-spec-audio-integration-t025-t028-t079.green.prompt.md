---
id: 0025
title: Cross-Spec Audio Integration T025 T028 T079
stage: green
date: 2026-03-04
surface: agent
model: claude-opus-4-6
feature: 001-willow-behavioral-framework
branch: 002-gemini-audio-opt
user: nabeera
command: Implement cross-spec integration seams T025 (flush audio buffer) and T028+T079 (preflight warmup)
labels: ["t025", "t028", "t079", "cross-spec", "audio-integration", "websocket", "fade-out", "preflight"]
links:
  spec: specs/002-gemini-audio-opt/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - src/main.py
  - src/tiers/tier4_sovereign.py
  - src/voice/static/noise-gate-processor.js
  - src/voice/static/audio_capture.js
  - src/config.py
  - tests/unit/test_audio_integration.py
  - specs/002-gemini-audio-opt/tasks.md
  - specs/001-willow-behavioral-framework/tasks.md
tests:
  - tests/unit/test_audio_integration.py (19 tests — 5 flush, 8 preflight, 2 config, 4 fade math)
  - tests/unit/ full suite (110 tests, all pass — zero regressions)
---

## Prompt

T035 connecting sovereign_truth.py to the audio pipeline, and the pre-flight warmup flag crossing from spec 002 into spec 001. Those are the two places where the architecture meets reality for the first time.

## Response snapshot

Implemented both cross-spec integration seams where the behavioral framework (spec 001) meets the audio pipeline (spec 002):

### Shared Infrastructure: Bidirectional WebSocket Protocol
- `voice_stream_handler()` in main.py now discriminates binary frames (audio) from text frames (JSON control messages)
- Added `_receive_message()` returning `Union[bytes, str, None]` — native WebSocket frame type discrimination
- Added `_handle_client_message()` for incoming control messages (preflight_start, preflight_end)
- Added `send_client_command()` for outgoing control messages (flush_audio_buffer)
- `_client_websocket` reference stored for server→client commands, cleaned up in finally block

### T025: Flush Audio Buffer (Tier 4 → AudioWorklet)
Full signal chain: Tier4Sovereign fires → `Tier4Result.flush_audio_buffer=True` → main.py calls `send_client_command("flush_audio_buffer", fade_duration_ms=7)` → browser calls `handleServerCommand(noiseGateNode, command)` → AudioWorklet `port.postMessage({type: 'flush'})` → NoiseGateProcessor applies per-sample linear fade-out over 7ms (336 samples at 48kHz) → gate closes cleanly.

- `Tier4Result`: Added `flush_audio_buffer: bool` field. True for non-vacuum fires, False for vacuum mode.
- `noise-gate-processor.js`: Added `port.onmessage` handler + fade-out state machine (`_fadingOut`, `_fadeTotalSamples`, `_fadeSamplesRemaining`). Linear ramp: `gain = remaining / total`. After fade completes, gate closes and hold resets.
- `audio_capture.js`: Added `handleServerCommand(noiseGateNode, command)` export for browser WebSocket client to forward server commands to AudioWorklet.

### T028 + T079: Preflight Warmup (Browser → Python → Tier 4)
Full signal chain: `initNoiseGate({onPreflightStart, onPreflightEnd})` → timer starts → `onPreflightStart()` callback → browser WS sends `{"type":"preflight_start"}` → Python `_handle_client_message` → `state_manager.set_preflight(True)` → Tier 4 `check_and_execute()` reads `state.preflight_active`, returns `None` → 3 seconds later → `onPreflightEnd()` → `set_preflight(False)` → Tier 4 enabled.

- `audio_capture.js`: `initNoiseGate()` accepts `{preflightDurationMs, onPreflightStart, onPreflightEnd}` options. Returns `preflightPromise` that resolves after warmup.
- `config.py`: Added `preflight_duration_ms: int = 3000` to `NoiseGateConfig`.
- Python side was 50% pre-built (SessionState.preflight_active, set_preflight(), Tier4 gate check) — this work connected the remaining signal path.

## Outcome

- ✅ Impact: Both cross-spec integration seams are wired end-to-end — architecture meets reality
- 🧪 Tests: 110/110 passing (91 existing + 19 new, zero regressions)
- 📁 Files: 6 modified/created, 2 tasks.md files updated (T025 [x], T028 [x], T079 [x])
- 🔁 Next prompts: Remaining 002 Phase 9 tasks (T024, T026, T027, T029); spec 001 T076 (Cold Start deferral)
- 🧠 Reflection: WebSocket binary/text frame discrimination is the natural protocol boundary for audio vs. control messages — no custom envelope needed. The lazy factory pattern from T035 extends naturally to cross-spec signal paths.

## Evaluation notes (flywheel)

- Failure modes observed: SovereignTruth constructor requires `contradiction_keywords` and `priority` fields — test fixtures must match the exact dataclass schema.
- Graders run and results (PASS/FAIL): pytest 110/110 PASS
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): T024 (configurable noise gate threshold) and T076 (Cold Start deferral for contradictions)

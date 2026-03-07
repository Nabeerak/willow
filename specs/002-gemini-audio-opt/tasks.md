# Tasks: Voice Session Audio Quality & Cost Optimization

**Feature**: `002-gemini-audio-opt`
**Input**: Design documents from `/specs/002-gemini-audio-opt/`
**Branch**: `002-gemini-audio-opt`
**Date**: 2026-03-02

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.
**Skill annotations**: Where a Claude skill accelerates delivery, it is noted as `[skill: name]` after the description.

---

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no blocking dependencies)
- **[Story]**: Which user story this task belongs to (US1–US5)
- Exact file paths are included in every description

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create new directories and verify environment before any code changes.

- [x] T001 Create static JS directory `src/voice/static/` with empty `.gitkeep`
- [x] T002 Verify `.env` contains `GEMINI_MODEL_ID` key (add placeholder if missing): `.env` — value must be set to a Gemini 2.5-series model ID before testing Phase 3

**Checkpoint**: Directory structure ready; `.env` prepared.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Config layer changes that all user stories depend on. Must complete before any story phase.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T003 Add `model_id: str` field with `from_env()` loading from `GEMINI_MODEL_ID` env var to `GeminiConfig` dataclass in `src/config.py` — default `"gemini-2.5-flash-preview-04-17"`
- [x] T004 [P] Add frozen `NoiseGateConfig` dataclass to `src/config.py` with fields `threshold_dbfs: float = -50.0` and `hold_ms: int = 200`
- [x] T005 [P] Add `noise_gate: NoiseGateConfig` field to `WillowConfig` dataclass and wire into `WillowConfig.from_env()` in `src/config.py`
- [x] T006 Update `StreamingSession.__init__()` in `src/voice/gemini_live.py` to accept `model_id` from `self._gemini_config.model_id` instead of the hardcoded default `"gemini-2.0-flash-exp"` at line 211

**Checkpoint**: Config layer updated; `StreamingSession` reads model from env. No story work should start before here.

---

## Phase 3: User Story 1 — Clean Voice Input Without Echo or Noise (Priority: P1) 🎯 MVP

**Goal**: Microphone input uses echo cancellation, noise gate suppresses background audio below -50 dBFS, and AudioWorklet keeps processing when the tab is backgrounded.

**Independent Test**: Open a browser, initialize the noise gate, play audio through speakers — agent voice must not re-enter the mic. Speak quietly below the threshold — no audio should appear in the gated stream. Tab-background the page — processing must continue.

**Skill**: `webapp-testing` for browser verification of AudioWorklet behavior

### Implementation for User Story 1

- [x] T007 [P] [US1] Create `src/voice/static/noise-gate-processor.js` — `AudioWorkletProcessor` subclass `NoiseGateProcessor` with:
  - `constructor`: `this._threshold = 0.003162` (-50 dBFS = 10^(-50/20)); `this._holdDurationSamples = Math.round(0.200 * sampleRate)`; `this._holdSamplesRemaining = 0`; `this._gateOpen = false`
  - `process(inputs, outputs, parameters)`: compute block RMS over 128 samples; open gate + reset hold if `rms >= threshold`; decrement hold and keep open if `holdSamplesRemaining > 0`; close gate if hold expired; copy input to output only when gate open; return `true`
  - End of file: `registerProcessor('noise-gate-processor', NoiseGateProcessor)`

- [x] T008 [P] [US1] Create `src/voice/static/audio_capture.js` — exported async function `initNoiseGate()` with:
  - `getUserMedia({ audio: { echoCancellation: true, noiseSuppression: false, autoGainControl: false }, video: false })`
  - `new AudioContext()`
  - `await audioContext.audioWorklet.addModule('noise-gate-processor.js')`
  - `new AudioWorkletNode(audioContext, 'noise-gate-processor')` with `onprocessorerror` handler
  - `audioContext.createMediaStreamDestination()`
  - Wire graph: `micSource.connect(noiseGateNode); noiseGateNode.connect(captureDestination)`
  - Return `{ audioContext, noiseGateNode, gatedStream: captureDestination.stream, stop }`
  - `stop()` releases mic tracks and closes AudioContext
  - `[skill: webapp-testing]`

- [x] T009 [US1] Add `AudioContext.resume()` guard to `initNoiseGate()` in `src/voice/static/audio_capture.js` — after `new AudioContext()`, check `audioContext.state === 'suspended'` and call `await audioContext.resume()` if true (handles autoplay policy restriction)

**Checkpoint**: Call `initNoiseGate()` in browser console. Echo cancellation prevents agent audio loopback. Gated stream produces silence when room is quiet. Processing continues when tab is backgrounded.

---

## Phase 4: User Story 2 — No Billing for Silence During Conversation (Priority: P2)

**Goal**: The noise gate reliably closes during sustained silence (>200ms), transmitting zero audio bytes to Gemini Live during quiet periods.

**Independent Test**: Start a voice session; stay silent for 5 seconds; verify the Gemini Live `stream()` method receives zero calls during that window. Resume speaking; verify `stream()` resumes within 200ms.

### Implementation for User Story 2

- [x] T010 [US2] Add hold-underflow guard in `noise-gate-processor.js`: ensure `this._holdSamplesRemaining = Math.max(0, this._holdSamplesRemaining - blockSize)` (prevents negative countdown values on variable block sizes) in `src/voice/static/noise-gate-processor.js`

- [x] T011 [P] [US2] Add `session_started_at: datetime` field (set in `connect()`) and `session_duration_seconds` computed property to `StreamingSession` in `src/voice/gemini_live.py` — used for monitoring; no caching API calls made

- [x] T012 [US2] Confirm silence gate and interruption handler do not conflict: add a comment block to `voice_stream_handler()` in `src/main.py` (lines 244–255) documenting that the noise gate operates client-side before bytes arrive; server-side `InterruptionHandler` receives no frames during silence, which is the correct behaviour — no code change needed, documentation only

**Checkpoint**: Monitor `StreamingSession.stream()` call frequency during a 5-second silence period. Call count must be 0.

---

## Phase 5: User Story 3 — Responsive Agent on Complex Questions (Priority: P3)

**Goal**: Every Gemini Live session initialises with `ThinkingConfig(thinking_level=MINIMAL, include_thoughts=True)`. Thought traces are filtered from the surface response accumulator.

**Independent Test**: Start a session with a 2.5-series model. Send a complex multi-step question. Verify `_accumulated_agent_response` contains no `[thought]`-tagged text and response latency is consistent across simple and complex turns.

### Implementation for User Story 3

- [x] T013 [US3] Add `thinking_config=genai_types.ThinkingConfig(thinking_level=genai_types.ThinkingLevel.MINIMAL, include_thoughts=True)` to `LiveConnectConfig` construction inside `StreamingSession.connect()` at line 334 in `src/voice/gemini_live.py`

- [x] T014 [US3] Filter thought parts in `StreamingSession._handle_server_content()` in `src/voice/gemini_live.py` at line 582:
  ```python
  # Replace:
  if part.text:
      self._accumulated_agent_response += part.text
  # With:
  if part.text:
      if getattr(part, 'thought', False):
          logger.debug(f"Thought trace ({len(part.text)} chars): {part.text[:80]}")
      else:
          self._accumulated_agent_response += part.text
  ```

- [x] T015 [P] [US3] Write unit tests in `tests/unit/test_gemini_live_thinking.py`:
  - `test_thinking_config_in_live_connect_config()` — mock `client.aio.live.connect`; assert `live_config.thinking_config.thinking_level == ThinkingLevel.MINIMAL`
  - `test_thought_parts_filtered()` — mock Part with `thought=True`; assert not in `_accumulated_agent_response`
  - `test_non_thought_parts_accumulated()` — mock Part with `thought=False`; assert text appears in `_accumulated_agent_response`
  - `[skill: webapp-testing]`

**Checkpoint**: Run `pytest tests/unit/test_gemini_live_thinking.py`. All 3 tests pass.

---

## Phase 6: User Story 4 — Long Conversations Stay Affordable (Priority: P4)

**Goal**: WebSocket connection is maintained continuously for the full session. No unnecessary reconnects that would discard server-side implicit context reuse.

**Independent Test**: Run a 15-minute session. Verify `connect()` is called exactly once and `disconnect()` exactly once. Zero `StreamingSessionError` exceptions from reconnect attempts.

### Implementation for User Story 4

- [x] T016 [US4] Strengthen the reconnect guard in `StreamingSession.connect()` in `src/voice/gemini_live.py` (lines 317–321): replace `logger.warning(...)` + `return` with a raised `StreamingSessionError` so callers cannot silently double-connect — include session_id and current state in the message

- [x] T017 [P] [US4] Add `session_duration_seconds` property to `StreamingSession` in `src/voice/gemini_live.py` that returns `(datetime.now(timezone.utc) - self._session_started_at).total_seconds()` when connected, else `0.0` — log at INFO level every 5 minutes via a background task started in `connect()`

**Checkpoint**: `session.session_duration_seconds` increments correctly. Second `connect()` call raises `StreamingSessionError`.

---

## Phase 7: User Story 5 — Voice Session Works When Tab Is Backgrounded (Priority: P5)

**Goal**: AudioWorklet audio processing (noise gate) and gated stream output continue uninterrupted when the browser tab loses focus or is minimized.

**Independent Test**: Start voice session; background the tab for 30 seconds; return and speak — full response received with no missed audio and no silent billing during the background period.

**Skill**: `webapp-testing` for automated Playwright tab-switching test

### Implementation for User Story 5

- [x] T018 [US5] Add `document.addEventListener('visibilitychange', ...)` handler in `src/voice/static/audio_capture.js` that logs `document.visibilityState` for diagnostics but performs **no action** on the AudioContext (AudioWorklet thread is unaffected by visibility — logging only confirms correct behaviour)

- [x] T019 [P] [US5] Write browser smoke test using `webapp-testing` skill: verify `noiseGateNode` is processing (non-zero output during speech) both before and after programmatic tab switch in a headless Chromium session — `[skill: webapp-testing]`

**Checkpoint**: Playwright test passes with tab-switch scenario. No audio processing interruption detected.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Math verification tests, documentation, and final validation pass.

- [x] T020 [P] Write `tests/unit/test_noise_gate_math.py` — pure Python assertions verifying:
  - `abs(10 ** (-50/20) - 0.003162) < 1e-6` (threshold)
  - `int(0.200 * 48000) == 9600` (hold at 48 kHz)
  - `int(0.200 * 16000) == 3200` (hold at 16 kHz)
  - `round(32768 * 10**(-50/20)) == 104` (16-bit scale sanity check)

- [x] T021 [P] Verify `src/config.py` `WillowConfig.validate()` covers `GeminiConfig.model_id` not empty — add validation if missing

- [x] T022 Run `quickstart.md` validation checklist manually: verify all 5 items (noise gate init, echo cancellation, backgrounding, thinking config, Python unit tests) produce expected results

- [x] T023 [P] Update `specs/002-gemini-audio-opt/checklists/requirements.md` — mark all implementation items resolved; add note that SC-002 was revised and FR-006 reflects implicit caching approach

**Checkpoint**: `pytest tests/unit/` passes. `quickstart.md` checklist complete. Feature branch ready for PR.

---

## Phase 9: Audio Hardening (Fixes Batch 2026-03-02)

**Purpose**: Address audio quality and resilience issues identified in the fixes batch. These tasks implement FR-009 through FR-013 from the updated spec.

- [x] T024 [P] Make noise gate threshold configurable in `src/voice/static/noise-gate-processor.js` — read `threshold_dbfs` from processor options instead of hardcoding `0.003162`; update `src/voice/static/audio_capture.js` `initNoiseGate()` to pass `NoiseGateConfig.threshold_dbfs` as processor option (FR-009)
- [x] T025 [P] Implement `flush_audio_buffer()` with 5-10ms linear fade-out in `src/voice/static/noise-gate-processor.js` — when gate closes or stream is cut, apply linear fade-out over the final samples instead of instant truncation; prevent audible click at waveform peak (FR-010). Cross-file call site: spec 001 `tier4_sovereign.py` sends `flush` command via WebSocket to browser; browser forwards to AudioWorklet via `noiseGateNode.port.postMessage({type: 'flush'})`; processor handles in `port.onmessage` and triggers fade-out
- [x] T026 [P] Make AudioWorklet buffer size configurable and adaptive in `src/voice/static/audio_capture.js` — initialize at 1024 samples, detect underrun events via AudioWorklet callbacks, drop to 512 only after 30 seconds of stable operation; add `buffer_size: int = 1024` to `NoiseGateConfig` in `src/config.py` (FR-011)
- [x] T027 [P] Add `enable_pitch_analysis: bool = False` feature flag to `NoiseGateConfig` in `src/config.py` — disabled by default for MVP, placeholder for future FFT pitch analysis at every-5th-frame sampling rate (FR-012)
- [x] T028 Implement 3-second pre-flight warmup in `src/voice/static/audio_capture.js` — noise gate runs during pre-flight but a `preflight_active` flag is exposed to Python layer so Tier 4 is disabled during this window; mirrors spec 001 Cold Start warmup (FR-013)
- [x] T029 Update Calibration Cohort testing to include soft-spoken test persona — verify threshold at -50dB doesn't gate legitimate soft speech; test at -40dB and -45dB alternatives (FR-009)

**Checkpoint**: All audio hardening FRs implemented. Soft-spoken persona passes Calibration Cohort. No buffer pops on stream cut. Adaptive buffer settles within 30 seconds.

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup)
  └── Phase 2 (Foundational) — BLOCKS all stories
        ├── Phase 3 (US1 — Noise Gate Core)    ← MVP
        ├── Phase 5 (US3 — Thinking Config)    ← can start in parallel with Phase 3
        └── Phase 6 (US4 — Connection Guard)   ← can start in parallel
              ├── Phase 4 (US2 — Silence Gate) ← depends on Phase 3 (T007/T008)
              └── Phase 7 (US5 — Backgrounding) ← depends on Phase 3 (T007/T008)
                    └── Phase 8 (Polish)
                          └── Phase 9 (Audio Hardening) ← depends on Phase 3 (T007/T008)
```

### User Story Dependencies

| Story | Depends on | Can run in parallel with |
|-------|-----------|--------------------------|
| US1 (P1) — Noise Gate Core | Phase 2 complete | US3, US4 |
| US2 (P2) — Silence Gating | US1 (T007, T008) | US3, US4 |
| US3 (P3) — Thinking Config | Phase 2 complete | US1, US4 |
| US4 (P4) — Connection Guard | Phase 2 complete | US1, US3 |
| US5 (P5) — Tab Backgrounding | US1 (T007, T008) | US3, US4 |

### Within-Story Task Order

- T007 and T008 are parallel (different files: `noise-gate-processor.js` vs `audio_capture.js`)
- T009 depends on T008 (extends `audio_capture.js`)
- T013 and T014 are sequential (both in `gemini_live.py`, T014 depends on T013 context)
- T015 can run in parallel with T013/T014 (separate test file, write tests before or after)

---

## Parallel Execution Examples

### MVP Sprint: US1 (Phase 3)

```
T007 → noise-gate-processor.js   (audio rendering thread logic)
T008 → audio_capture.js          (main-thread setup)           } run in parallel
```
After both complete: T009 (AudioContext resume guard, extends T008)

### Backend Sprint: US3 (Phase 5)

```
T013 → add ThinkingConfig to LiveConnectConfig
T014 → filter thought parts (depends on T013 being in place conceptually)
T015 → write unit tests                                          } parallel with T013/T014
```

---

## Skill Index

| Skill | Tasks | Purpose |
|-------|-------|---------|
| `webapp-testing` | T008, T015, T019 | Playwright browser automation for AudioWorklet, thought-part filtering verification, tab-switch test |
| `sp.implement` | All | Primary execution skill for code generation |

---

## Implementation Strategy

### MVP (User Story 1 Only)

1. Phase 1 (T001–T002)
2. Phase 2 (T003–T006)
3. Phase 3 (T007–T009) — **STOP and VALIDATE**
4. Noise gate works in browser — ship or demo

### Full Feature

1. MVP above
2. Phase 4 (T010–T012) — silence billing suppression
3. Phase 5 (T013–T015) — thinking config (requires 2.5-series model in `.env`)
4. Phase 6 (T016–T017) — connection resilience
5. Phase 7 (T018–T019) — backgrounding verification
6. Phase 8 (T020–T023) — polish and tests
7. Phase 9 (T024–T029) — audio hardening (configurable threshold, fade-out, adaptive buffer, pre-flight warmup)

---

## Notes

- `[P]` tasks touch different files — safe to run in parallel
- `[US*]` label maps each task to the user story it delivers
- AudioWorklet (T007) is pure JS with no external dependencies — can be implemented offline
- Thinking config (T013) silently does nothing if `GEMINI_MODEL_ID` is not set to a 2.5-series model in `.env`
- Implicit caching requires no code — just keeping the WebSocket alive (T016/T017)
- Total tasks: **29** across 9 phases

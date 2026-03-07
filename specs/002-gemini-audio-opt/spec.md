# Feature Specification: Voice Session Audio Quality & Cost Optimization

**Feature Branch**: `002-gemini-audio-opt`
**Created**: 2026-03-01
**Status**: Draft
**Input**: User description: "Configure Gemini Live API with thinking_level: MINIMAL and include_thoughts: true; add client-side noise gate (RMS -50dB, 200ms hold/release); set echoCancellation: true in getUserMedia; implement VAD-based audio stream gating; add Context Caching for sessions >10 min; use AudioWorklet instead of ScriptProcessor; include thinking_config in gemini_live.py session initialization."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Clean Voice Input Without Echo or Noise (Priority: P1)

A user engages Willow in a voice conversation in a typical home or office environment. Background sounds (fans, keyboard clicks, ambient noise) and the agent's own voice output should not be picked up and sent to the voice session. The user's words — and only those words — are what the agent receives and processes.

**Why this priority**: Audio echo and background noise directly degrade response quality and inflate per-conversation costs. Eliminating them is foundational to a usable voice experience and all other stories depend on clean audio input.

**Independent Test**: Can be fully tested by starting a voice session, playing audio from the device speakers, and verifying the agent does not react to its own voice or ambient background sounds.

**Acceptance Scenarios**:

1. **Given** a voice session is active and the agent is speaking, **When** the agent's audio plays through device speakers, **Then** the microphone input does not capture the agent's voice and no self-triggered response is generated.
2. **Given** a quiet room with ambient noise below the background threshold, **When** the user is not speaking, **Then** no audio data is transmitted to the voice session and no tokens are billed.
3. **Given** the user begins speaking after a short pause, **When** speech energy rises above the detection threshold and persists for the hold period, **Then** audio transmission resumes within 200ms without clipping the beginning of the utterance.

---

### User Story 2 - No Billing for Silence During Conversation (Priority: P2)

A user pauses mid-conversation to think, look something up, or wait. During this silence, no audio data should be transmitted and no voice tokens should be consumed. When the user resumes speaking, the session reconnects seamlessly without the user noticing any interruption.

**Why this priority**: The voice API bills at a fixed rate per second of audio streamed. Transmitting silence wastes budget directly. This story reduces operational cost for every session.

**Independent Test**: Can be tested by conducting a 5-minute session with 2 minutes of deliberate silence, then verifying the billed duration is approximately 3 minutes.

**Acceptance Scenarios**:

1. **Given** the user stops speaking for more than 200ms, **When** silence is confirmed by the noise gate hold timer, **Then** the audio stream is paused and no audio data is sent to the voice session.
2. **Given** the audio stream has been paused due to silence, **When** the user begins speaking again, **Then** the stream resumes within one hold-period (200ms) and captures the full utterance.
3. **Given** a voice session with extended silence periods, **When** the session ends, **Then** the billed audio duration reflects only the periods when speech was actively transmitted.

---

### User Story 3 - Responsive Agent on Complex Questions (Priority: P3)

A user asks Willow a nuanced or multi-step question during a voice conversation. The agent should reason through the answer without introducing perceptible lag caused by switching between reasoning modes mid-session. The response should feel fluid even for questions that require deeper analysis.

**Why this priority**: Reasoning latency degrades conversational naturalness. Enabling lightweight reasoning from session start avoids the latency spike of activating it on demand mid-conversation.

**Independent Test**: Can be tested by asking a series of progressively complex questions in a single session and measuring whether response latency remains consistent.

**Acceptance Scenarios**:

1. **Given** a voice session is initialized, **When** the user asks a simple factual question, **Then** the response begins within the expected latency window without a warm-up delay.
2. **Given** a voice session is active, **When** the user asks a complex multi-step reasoning question, **Then** the agent provides a coherent response without noticeably longer latency than simpler questions.
3. **Given** a session configured for reasoning capability from initialization, **When** multiple turns occur, **Then** latency between turns remains consistent and does not degrade across the conversation.

---

### User Story 4 - Long Conversations Stay Affordable (Priority: P4)

A user has an extended voice session lasting more than 10 minutes — for example, a coaching session, a learning session, or a deep problem-solving conversation. The cost of maintaining context across turns should not scale linearly with session length.

**Why this priority**: Without cost controls, long sessions become prohibitively expensive to operate. Context caching reduces the per-turn cost for repeat context by up to 90%, directly enabling longer session viability.

**Independent Test**: Can be tested by running an identical 15-minute test session with and without caching enabled, then comparing reported token costs.

**Acceptance Scenarios**:

1. **Given** a session has been running for more than 10 minutes, **When** subsequent turns are processed, **Then** the cost of repeated context is significantly lower than in sessions without caching.
2. **Given** a cached context exists for the current session, **When** the session continues past the caching threshold, **Then** new turns reference the cached context without loss of conversational coherence.
3. **Given** a session that crosses the 10-minute mark mid-conversation, **When** caching is activated, **Then** the user experiences no interruption or change in response behavior.

---

### User Story 5 - Voice Session Works When Tab Is Backgrounded (Priority: P5)

A user starts a voice conversation and then switches to another browser tab or minimizes the window. The noise gate and audio processing should continue functioning normally — silence should still suppress transmission, and the user's speech when returning should still be detected and transmitted correctly.

**Why this priority**: Browser tab backgrounding is a common real-world scenario. Loss of audio processing in this state would result in silent token billing during backgrounded periods and potential missed speech upon return.

**Independent Test**: Can be tested by starting a voice session, backgrounding the tab, speaking after 30 seconds, and verifying the response was received and no silence tokens were billed during the background period.

**Acceptance Scenarios**:

1. **Given** a voice session is active and the browser tab is moved to the background, **When** the user is silent, **Then** no audio data is transmitted and no tokens are billed.
2. **Given** a voice session is active and the browser tab is backgrounded, **When** the user speaks, **Then** the audio is captured, transmitted, and the agent responds correctly.
3. **Given** a backgrounded tab with an active voice session, **When** the tab is brought back to the foreground, **Then** audio processing continues without interruption or reconfiguration.

---

### Edge Cases

- **EC-001 — Threshold Hover**: When the user is speaking quietly and RMS energy hovers near the detection threshold, the 200ms hold/release prevents rapid gate open/close oscillation.
- **EC-002 — Caching Failure**: When caching fails to activate after 10 minutes, session continues without caching; cost is higher but functionality is unaffected.
- **EC-003 — Word Clipping**: When the noise gate suppresses the start of a word, the hold period ensures transmission begins within 200ms of speech onset, preventing word clipping.
- **EC-004 — Background Tab Audio**: When the browser tab is backgrounded during an active audio burst, AudioWorklet processing continues in a separate thread, preserving gate behavior.
- **EC-005 — Echo Contamination**: When the agent is speaking and the noise gate opens due to background noise, echo cancellation in the audio capture pipeline prevents agent audio from reaching the noise gate input.
- **EC-006 — Caching Boundary**: When a session reaches the caching threshold exactly at a turn boundary, caching activates cleanly at the next turn without affecting the in-progress response.
- **EC-007 — Gate Clipping (Soft-Spoken Users)**: When the -50dB threshold is too aggressive for soft-spoken users, their speech is gated as silence. **Resolution**: `threshold_dbfs` is configurable via environment variable with -50dB as default. Stored in `NoiseGateConfig.threshold_dbfs: float = -50.0`. Calibration Cohort testing MUST include a soft-spoken test persona to catch this before submission.
- **EC-008 — Buffer Pop (Stream Cut at Waveform Peak)**: When the audio stream is cut at a waveform peak, an audible click breaks the premium voice feel. **Resolution**: `flush_audio_buffer()` MUST implement a 5-10ms linear fade-out before cutting, not an instant truncation. This ensures clean audio transitions when Tier 4 fires or when the stream is gated.
- **EC-009 — Fade-out Latency (Hardware Buffer)**: When hardware buffer exceeds 1024 samples, the software fade-out is ignored and the pop occurs at OS level. **Resolution**: set hardware buffer size to a maximum of 512 samples in AudioWorklet initialization. Add `buffer_size` as a configurable parameter in `NoiseGateConfig` with a hard cap.
- **EC-010 — CPU Overhead (FFT on Every Frame)**: Running FFT pitch analysis on every audio frame on low-end mobile is a performance risk. **Resolution**: for MVP, FFT-based pitch analysis is disabled entirely. Feature flag in `NoiseGateConfig`: `enable_pitch_analysis: bool = False` — off by default. MVP relies on the 2-keyword dual-gate and interrogative structure detection in spec 001 instead. FFT sampling (every 5th frame) deferred to future version.
- **EC-011 — Audio Dropout Risk (512 Buffer on Mobile)**: 512 samples is aggressive for mobile browsers and may cause audio dropouts. **Resolution**: do not hardcode 512 — make buffer adaptive. Start at 1024, detect dropout events via AudioWorklet underrun callbacks, and only drop to 512 if hardware proves stable after 30 seconds. `NoiseGateConfig.buffer_size: int = 1024` with a note that 512 is available for low-latency environments only.
- **EC-012 — The 30-Second Gap (Pre-Flight Buffer Settlement)**: In the first 10 seconds, the buffer hasn't settled and echo or pop events are likely before the 512-sample state stabilizes. **Resolution**: add a 3-second pre-flight warmup period before the session is considered "live" — mirrors the Cold Start warmup (d=0 for first 3 turns) in spec 001. During pre-flight, noise gate runs but Tier 4 is disabled. `localStorage` persistence for buffer state is deferred to future version.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The voice session MUST initialize with on-demand reasoning capability enabled from the start so that complex turns receive analytical support without a latency spike from runtime activation.
- **FR-002**: The voice session MUST suppress audio transmission when measured speech energy is below the configured silence threshold (-50dB RMS equivalent) for longer than 200ms, preventing silent audio from being billed.
- **FR-003**: The audio capture pipeline MUST use echo cancellation so the agent's own voice output does not re-enter the audio input and trigger unintended responses or noise gate behavior.
- **FR-004**: The noise gate MUST use a 200ms hold timer before closing after speech ends, preventing gate jitter during natural speech pauses and mid-word silences.
- **FR-005**: The noise gate and audio processing pipeline MUST continue functioning when the browser tab is backgrounded or loses focus.
- **FR-006**: Voice sessions MUST maintain a continuous WebSocket connection for their full duration without unnecessary reconnects, preserving the server's automatic context reuse across turns.
- **FR-007**: The VAD silence detection MUST integrate with the existing interruption handler so that stream closure during silence does not conflict with agent-interruption logic.
- **FR-008**: The reasoning configuration MUST be included in the session initialization parameters at the start of every session, not added retroactively after connection.
- **FR-009**: The noise gate threshold MUST be configurable via environment variable, not hardcoded. Default is -50dB (`NoiseGateConfig.threshold_dbfs: float = -50.0`). Calibration Cohort testing MUST include a soft-spoken test persona.
- **FR-010**: `flush_audio_buffer()` MUST implement a 5-10ms linear fade-out before cutting the audio stream. Instant truncation at a waveform peak is not permitted — it causes an audible click that degrades voice quality.
- **FR-011**: AudioWorklet buffer size MUST be configurable via `NoiseGateConfig.buffer_size: int = 1024` with adaptive behavior: start at 1024 samples, detect dropout events via underrun callbacks, drop to 512 only if hardware proves stable after 30 seconds. 512 is the hard floor — no buffer below 512 is permitted.
- **FR-012**: FFT-based pitch analysis MUST be disabled by default for MVP. Feature flag: `NoiseGateConfig.enable_pitch_analysis: bool = False`. When enabled in future versions, sample every 5th frame only (80% CPU reduction).
- **FR-013**: The session MUST implement a 3-second pre-flight warmup period before the session is considered "live". During pre-flight, noise gate runs but Tier 4 (from spec 001) is disabled. This mirrors spec 001 Cold Start warmup and allows hardware buffer to settle.

### Key Entities

- **Voice Session**: A real-time bidirectional audio conversation between the user and Willow, bounded by connection and disconnection events. Has a state (connecting, connected, streaming, etc.), duration, and accumulated token cost.
- **Noise Gate**: A signal processing component that monitors incoming audio energy levels and opens or closes the audio transmission path based on configurable thresholds and timing.
- **Audio Token**: A unit of billing for real-time voice API usage, consumed at a fixed rate per second of audio data transmitted regardless of content.
- **Voice Activity Detection (VAD)**: The process of classifying audio frames as speech or silence. Used to open/close the noise gate and determine when to close the audio stream.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Sessions with 50% silence time bill no more than 55% of the equivalent fully-active session cost (allowing a small buffer for gate hold periods).
- **SC-002**: Voice sessions maintain a stable WebSocket connection for their full duration without unnecessary reconnects, ensuring the server's automatic context reuse is not disrupted; verified by zero unintended reconnects in sessions lasting 10–30 minutes.
- **SC-003**: Response latency across turns within a single session varies by no more than 20% between simple and complex questions, measured over 10 representative test sessions.
- **SC-004**: Zero agent self-interruptions occur in test sessions where the agent's audio is played through the same device receiving microphone input.
- **SC-005**: 100% of audio processing and noise gate functions operate correctly when the browser tab is backgrounded, verified by functional test with tab switching.
- **SC-006**: Speech onset is captured within 200ms of the user beginning to speak, with no word clipping detectable in the transmitted audio.

## Assumptions

- The existing `src/voice/interruption_handler.py` VAD implementation will be extended or coordinated with, not replaced.
- The existing `src/voice/gemini_live.py` `StreamingSession.connect()` method is the correct integration point for session initialization parameters.
- Browser-side audio capture (getUserMedia, AudioWorklet) is the delivery mechanism for audio to the pipeline.
- "Sessions exceeding 10 minutes" refers to wall-clock duration from connection, not active speaking time.
- Context reuse in Gemini Live sessions is handled automatically server-side (implicit caching); no explicit caching API call is required or available for Live API WebSocket sessions.
- The -50dB RMS threshold is the target noise floor; the float32 AudioWorklet equivalent is 0.003162 (verified: 10^(-50/20)); the 16-bit PCM equivalent is ~104 counts (not 18 as originally estimated).

## Out of Scope

- Transcription accuracy improvements (handled separately)
- Multi-speaker detection or speaker diarization
- Changes to the agent's behavioral tiers or M-modifier logic
- Server-side audio processing or noise reduction
- Support for audio formats other than 16kHz 16-bit PCM mono
- FFT-based pitch analysis for intonation detection (deferred — MVP uses `enable_pitch_analysis: False`)
- localStorage persistence for audio buffer state (deferred — pre-flight warmup is sufficient for MVP)
- Adaptive buffer below 512 samples

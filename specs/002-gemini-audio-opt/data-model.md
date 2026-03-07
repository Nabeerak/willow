# Data Model: Voice Session Audio Quality & Cost Optimization

**Feature**: 002-gemini-audio-opt
**Date**: 2026-03-02

This feature introduces no new persistent data entities. All state is transient (per-session) or configuration. This document describes the key runtime data structures and their relationships.

---

## Entities

### NoiseGateState (Client-side, JavaScript)

Runtime state maintained within the `NoiseGateProcessor` AudioWorklet.

| Field | Type | Description |
|-------|------|-------------|
| `threshold` | `float` | -50 dBFS as float32 linear amplitude = `0.003162` |
| `holdDurationSamples` | `int` | `Math.round(0.200 * sampleRate)` — 200ms in samples |
| `holdSamplesRemaining` | `int` | Countdown: samples remaining in hold period (≥0) |
| `gateOpen` | `bool` | Current gate state: `true` = passing audio, `false` = suppressed |

**Transitions:**
```
rms >= threshold          → gateOpen = true, reset holdSamplesRemaining
rms < threshold AND hold > 0 → gateOpen = true, decrement hold by blockSize (128)
rms < threshold AND hold = 0 → gateOpen = false
```

**Invariants:**
- `holdSamplesRemaining` never goes below 0
- `gateOpen` can only change state once per 128-sample block
- Output buffer is pre-zeroed by browser; writes are only performed when `gateOpen = true`

---

### ThinkingSessionConfig (Server-side, Python — new config slice)

Configuration for the Gemini Live API thinking features. Added to `LiveConnectConfig` at session initialization.

| Field | Type | Value |
|-------|------|-------|
| `thinking_level` | `ThinkingLevel` | `ThinkingLevel.MINIMAL` |
| `include_thoughts` | `bool` | `True` |

**Note**: `ThinkingLevel.MINIMAL` is a valid `CaseInSensitiveEnum` value in the installed google-genai SDK. It maps to the string `'MINIMAL'`, which the SDK serializes to `thinkingConfig.thinkingLevel` in the WebSocket setup message.

**Model dependency**: Thinking requires Gemini 2.5-series models. Current default `gemini-2.0-flash-exp` must be updated to a 2.5-series model (e.g., `gemini-2.5-flash-preview`) for thinking to activate. If an unsupported model is used, the `thinking_config` field is silently ignored by the API.

---

### AudioCaptureConfig (Client-side, JavaScript — getUserMedia constraints)

Configuration passed to `navigator.mediaDevices.getUserMedia()`.

| Constraint | Value | Rationale |
|-----------|-------|-----------|
| `echoCancellation` | `true` | Browser AEC DSP removes agent audio from mic input before it reaches the noise gate |
| `noiseSuppression` | `false` | Noise gate handles suppression; browser suppression can conflict by pre-boosting quiet audio above threshold |
| `autoGainControl` | `false` | Prevents AGC from amplifying silence above -50 dBFS threshold |

---

### SessionDurationTracker (Server-side, Python — optional monitoring)

Runtime tracking for session duration, used to monitor whether implicit caching is likely active (no direct caching API exists for Live sessions).

| Field | Type | Description |
|-------|------|-------------|
| `session_start_time` | `datetime` | UTC timestamp of `connect()` call |
| `session_duration_seconds` | `float` (computed) | `(now - session_start_time).total_seconds()` |
| `implicit_caching_likely` | `bool` (computed) | Heuristic: `session_duration_seconds > 600` (10 min) |

**Note**: This is an informational-only monitor. No caching API calls are made. Implicit caching is managed entirely server-side by Google's infrastructure.

---

## Entity Relationships

```
AudioCaptureConfig (getUserMedia constraints)
  └── feeds → MediaStreamAudioSourceNode
                └── feeds → NoiseGateState (AudioWorkletProcessor)
                              └── gates → gated MediaStream
                                           └── consumed by → Gemini Live stream sender
                                                              └── streams to → StreamingSession (Python backend)

StreamingSession (Python)
  └── initialized with → ThinkingSessionConfig (in LiveConnectConfig.thinking_config)
  └── monitored by → SessionDurationTracker (optional)
  └── receives interruptions from → InterruptionHandler (existing, unchanged)

NoiseGateState (client)
  └── independent of → InterruptionHandler (server)
  (VAD responsibilities are separated by execution layer — no shared state)
```

---

## Spec Corrections Identified During Research

1. **-50 dBFS on 16-bit scale**: The spec Assumptions section states "approximately 18 on a 0–32768 scale." The correct value is **~104** (`32768 × 0.003162`). The figure 18 corresponds to approximately -65.2 dBFS. This does not affect the AudioWorklet implementation, which operates entirely in float32 `[-1.0, 1.0]` range using `0.003162` as the threshold.

2. **Context caching**: The spec states "Context Caching should be implemented for sessions exceeding 10 minutes." The correct implementation action is **maintaining the WebSocket connection** (not calling any caching API). `LiveConnectConfig` has no `cached_content` field; implicit caching is automatic. SC-002 (≥80% cost reduction) is not directly achievable via explicit caching in the current architecture.

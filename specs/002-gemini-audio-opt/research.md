# Research: Voice Session Audio Quality & Cost Optimization

**Feature**: 002-gemini-audio-opt
**Date**: 2026-03-02
**Branch**: 002-gemini-audio-opt

---

## R1: Gemini Live API — Thinking Configuration

### Decision
Use `genai_types.ThinkingConfig(thinking_level=genai_types.ThinkingLevel.MINIMAL, include_thoughts=True)` in `LiveConnectConfig.thinking_config`.

### Verified Facts (from installed google-genai SDK at `/home/nabeera/.local/lib/python3.12/site-packages/google/genai/types.py`)

**`ThinkingConfig` class fields:**
```python
class ThinkingConfig:
    include_thoughts: Optional[bool]    # True = surface thought traces in response parts
    thinking_budget: Optional[int]      # 0 = DISABLED, -1 = AUTOMATIC, positive int = token cap
    thinking_level: Optional[ThinkingLevel]  # HIGH, MEDIUM, LOW, MINIMAL, THINKING_LEVEL_UNSPECIFIED
```

**`ThinkingLevel` enum (CaseInsensitiveEnum):**
- `MINIMAL` — confirmed valid value in installed SDK
- `LOW`, `MEDIUM`, `HIGH`, `THINKING_LEVEL_UNSPECIFIED` also valid

**Live API integration (from `_live_converters.py` lines 237–238, 688–691):**
```python
# thinking_config is serialized into setup.generationConfig.thinkingConfig
# Field name on LiveConnectConfig: thinking_config (snake_case)
```

**Correct Python code for `StreamingSession.connect()`:**
```python
live_config = genai_types.LiveConnectConfig(
    response_modalities=["AUDIO"],
    thinking_config=genai_types.ThinkingConfig(
        thinking_level=genai_types.ThinkingLevel.MINIMAL,
        include_thoughts=True,
    ),
    speech_config=genai_types.SpeechConfig(
        voice_config=genai_types.VoiceConfig(
            prebuilt_voice_config=genai_types.PrebuiltVoiceConfig(
                voice_name="Aoede"
            )
        )
    )
)
```

### Model Dependency
Thinking support requires **Gemini 2.5-series models**. The current default `gemini-2.0-flash-exp` (`src/voice/gemini_live.py:212`) may silently ignore `thinking_config`. Implementation must document the model requirement and update the default model ID or make it configurable.

**Rationale**: `MINIMAL` provides on-demand reasoning without the per-token overhead of full thinking. `include_thoughts=True` surfaces reasoning traces to enable downstream filtering in the response loop.

**Alternatives considered:**
- `thinking_budget=0` (disable): eliminates reasoning entirely — rejected; spec requires on-demand capability
- `thinking_budget=1024` (integer): also valid but `thinking_level` enum is more explicit and portable across SDK versions

---

## R2: Context Caching for Long Sessions

### Decision
**Rely on implicit server-side caching only.** The standard `CachedContent` REST API is incompatible with Live API WebSocket sessions. Explicit caching via `LiveConnectConfig` does not exist.

### Verified Facts

**Standard `CachedContent` API (client.caches.create):**
- Purpose: pre-cache large static content for `generate_content` REST calls
- Minimum: 32,768 tokens
- Cost: ~25% of standard input token price (75% reduction, not 90%)
- **Incompatible with Live API** — `LiveConnectConfig` has no `cached_content` field

**Live API implicit caching:**
- Automatic, zero configuration
- Server-side: activates when a repeated prompt prefix matches an internal threshold
- Session-scoped: discarded when WebSocket connection closes
- No user-visible signal: cannot observe whether it fired or what it saved
- Supported on `gemini-2.0-flash-exp` and 2.5-series models

**Impact on spec:**
- SC-002 ("sessions >10 minutes show ≥80% reduction in per-turn context token cost") is **not achievable** via explicit caching in the current architecture
- Implicit caching provides some automatic benefit but is not measurable or configurable
- Spec Assumptions line about "Context Caching should be implemented" requires revision: the implementation action is keeping the WebSocket connection alive (minimizing reconnects), not calling any caching API

### Alternatives Considered
| Option | Achievable? | Notes |
|--------|------------|-------|
| `client.caches.create()` + Live API | No | `LiveConnectConfig` has no `cached_content` field |
| Hybrid REST+Live (pre-process with CachedContent, then voice-only Live) | Yes, but architectural shift | Significant design change; deferred |
| Implicit caching (current) | Yes, automatically | Zero effort; savings are opaque |
| Minimize reconnects | Yes | Existing `StreamingSession` keeps one connection per session; correct approach |

**Rationale**: Attempting to add explicit caching to the Live API would require a fundamental architectural change (hybrid REST+Live). This is out of scope for the current feature; the plan documents implicit caching as the implementation and flags SC-002 as requiring revision.

> 📋 **Architectural decision detected**: Standard `CachedContent` is incompatible with Gemini Live API sessions; achieving measurable cost reduction requires either relying on implicit server-side caching or adopting a hybrid REST+Live architecture.
> Document reasoning and tradeoffs? Run `/sp.adr live-api-caching-architecture`

---

## R3: AudioWorklet Noise Gate

### Decision
Implement a client-side `NoiseGateProcessor` using `AudioWorkletProcessor`. Configure getUserMedia with `echoCancellation: true`, `noiseSuppression: false`, `autoGainControl: false`.

### Verified Facts

**-50 dBFS threshold (computed):**
```
linear = 10^(-50/20) = 10^(-2.5) = 0.003162...
```
- Float32 AudioWorklet threshold: `0.003162` (range: [-1.0, 1.0] where 0 dBFS = 1.0)
- 16-bit PCM equivalent: `32768 × 0.003162 ≈ 103.6` (~104 counts, not "~18" as in spec assumptions)
- The spec assumption of "~18 on 16-bit scale" is incorrect; 18/32768 = -65.2 dBFS

**200ms hold timer (computed):**
| Sample Rate | Hold samples | Blocks (128/block) |
|-------------|-------------|-------------------|
| 16,000 Hz   | 3,200       | 25                |
| 44,100 Hz   | 8,820       | ~69               |
| 48,000 Hz   | 9,600       | 75                |

**AudioWorklet vs ScriptProcessor:**
- `ScriptProcessorNode`: runs on main JS thread → throttled when tab is backgrounded
- `AudioWorkletProcessor`: runs on dedicated audio rendering thread → **unaffected by tab visibility**
- `registerProcessor()` is the global function to register; it must appear at end of processor file

**getUserMedia constraints — correct form:**
```javascript
navigator.mediaDevices.getUserMedia({
  audio: {
    echoCancellation: true,    // removes agent audio from mic input (AEC DSP)
    noiseSuppression: false,   // our gate handles suppression; browser's can interfere
    autoGainControl: false     // prevent AGC from boosting quiet audio above threshold
  },
  video: false
})
```

**Audio graph:**
```
getUserMedia (mic)
  → MediaStreamAudioSourceNode
  → AudioWorkletNode('noise-gate-processor')
  → MediaStreamAudioDestinationNode → .stream (gated MediaStream)
```

**Complete processor logic (verified against MDN Web Audio API spec):**
```javascript
class NoiseGateProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super(options);
    this._threshold = 0.003162;                          // -50 dBFS
    this._holdDurationSamples = Math.round(0.200 * sampleRate);  // 200ms
    this._holdSamplesRemaining = 0;
    this._gateOpen = false;
  }

  process(inputs, outputs, parameters) {
    const inChannel = inputs[0]?.[0];
    const outChannel = outputs[0]?.[0];
    if (!inChannel || !outChannel) return true;

    const N = inChannel.length;  // 128 samples per block
    let sumSq = 0;
    for (let i = 0; i < N; i++) sumSq += inChannel[i] * inChannel[i];
    const rms = Math.sqrt(sumSq / N);

    if (rms >= this._threshold) {
      this._gateOpen = true;
      this._holdSamplesRemaining = this._holdDurationSamples;
    } else if (this._holdSamplesRemaining > 0) {
      this._holdSamplesRemaining -= N;
      this._gateOpen = true;
    } else {
      this._gateOpen = false;
    }

    if (this._gateOpen) {
      for (let i = 0; i < N; i++) outChannel[i] = inChannel[i];
    }
    // else: outChannel pre-zeroed by browser — silence output is automatic

    return true;  // keep node alive
  }
}
registerProcessor('noise-gate-processor', NoiseGateProcessor);
```

**Rationale**: AudioWorklet is the only Web Audio API mechanism that survives tab backgrounding, meeting SC-005. The 200ms hold prevents gate chatter during natural speech pauses, meeting SC-006.

---

## R4: VAD Integration with Existing InterruptionHandler

### Decision
The existing `InterruptionHandler` in `src/voice/interruption_handler.py` performs server-side energy-based VAD for interruption detection. The new noise gate performs client-side VAD for audio transmission gating. These are **separate responsibilities on separate execution layers** and should remain independent — no code merge needed.

### Analysis

**Existing `InterruptionHandler` VAD** (`src/voice/interruption_handler.py`):
- Purpose: detect user speech during agent response to trigger interruption
- Layer: Python backend, processes audio after it arrives at the server
- Thresholds: `DEFAULT_SPEECH_THRESHOLD = 500.0` RMS (16-bit PCM scale, 0–32768)
- Output: fires `handle_interruption()` → callback to stop agent speaking

**New Noise Gate VAD**:
- Purpose: suppress audio transmission during silence to avoid billing silent tokens
- Layer: JavaScript client-side, processes audio before it leaves the browser
- Threshold: `-50 dBFS = 0.003162` float32
- Output: closes `AudioWorkletNode` output (stops sending audio)

**Coordination needed**: When the noise gate closes (user silent), no audio bytes reach the server. The `InterruptionHandler` will see no frames during silence, which is correct — it is already designed to accumulate silence frames and detect timeout. No code changes to `InterruptionHandler` are required for this feature.

**FR-007 resolution**: "VAD integration" means ensuring the noise gate does not interfere with interruption detection. Since they operate on different layers with different inputs, no integration code is needed — they are naturally isolated.

# Implementation Plan: Voice Session Audio Quality & Cost Optimization

**Branch**: `002-gemini-audio-opt` | **Date**: 2026-03-02 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/002-gemini-audio-opt/spec.md`

---

## Summary

Add thinking configuration (`ThinkingLevel.MINIMAL`, `include_thoughts=True`) to Gemini Live API session initialization in `src/voice/gemini_live.py`, implement a client-side AudioWorklet noise gate (-50 dBFS threshold, 200ms hold/release, echo cancellation) to suppress silent audio transmission, and filter thought parts from the surface response accumulator. Implicit server-side caching is already active and requires no code changes beyond maintaining WebSocket connection continuity (current architecture is correct).

---

## Technical Context

**Language/Version**: Python 3.12 (backend) · JavaScript ES2022 (AudioWorklet, no transpile)
**Primary Dependencies**: `google-genai >= 0.3.0` (installed), Web Audio API (browser-native)
**Storage**: N/A — all state is transient per-session
**Testing**: `pytest`, `pytest-asyncio` (existing); manual browser testing for AudioWorklet
**Target Platform**: Linux server (backend) · Chrome/Firefox browser (client AudioWorklet)
**Project Type**: Single project (Python backend + static JS client)
**Performance Goals**:
- Noise gate hold ≤200ms (speech onset to transmission start)
- Thinking config adds zero per-turn latency (configured at session init)
- Gated stream produces no bytes during silence (verified via packet inspection)
**Constraints**:
- `ThinkingLevel.MINIMAL` requires Gemini 2.5-series model (not `gemini-2.0-flash-exp`)
- AudioWorklet requires HTTPS in production; secure context in browser
- Standard `CachedContent` API incompatible with Live API — not usable
**Scale/Scope**: Affects all new voice sessions; single-session scope; ~3 files changed

---

## Constitution Check

*GATE: Must pass before proceeding to implementation.*

| Check | Result | Notes |
|-------|--------|-------|
| Tier 1 <50ms budget | ✅ PASS | Noise gate is client-side JS; no server-side Tier 1 impact |
| Tier 2 <5ms budget | ✅ PASS | ThinkingConfig is session init only; zero per-turn overhead |
| Tier 3/4 latency masked by filler | ✅ PASS | MINIMAL thinking minimizes latency delta; existing filler mechanism unchanged |
| ±2.0 state change cap | ✅ PASS | Not affected |
| Residual Plot / Decay formula | ✅ PASS | Not affected |
| Thought filtering | ✅ REQUIRES ACTION | `include_thoughts=True` means thought parts must be filtered from `_accumulated_agent_response` before surface text is used for behavior processing |
| No unverified API assumptions | ✅ PASS | All SDK fields verified against installed `google.genai.types` |
| Voice I/O via Gemini Live API | ✅ PASS | Feature enhances existing Live API integration |

**Gate violations**: None. One implementation requirement identified (thought filtering in `_handle_server_content`).

---

## Project Structure

### Documentation (this feature)

```text
specs/002-gemini-audio-opt/
├── spec.md              # Feature requirements
├── plan.md              # This file
├── research.md          # Phase 0 findings (ThinkingConfig, caching, AudioWorklet)
├── data-model.md        # Runtime data structures and relationships
├── quickstart.md        # Developer setup and testing guide
├── contracts/
│   ├── noise_gate.yaml         # NoiseGate AudioWorklet interface contract
│   └── thinking_session.yaml   # ThinkingConfig + caching contract
└── tasks.md             # Phase 2 output (/sp.tasks — not yet created)
```

### Source Code (repository root)

```text
src/
├── config.py                    # [MODIFY] Add GEMINI_MODEL_ID env var to GeminiConfig
│                                #          Add NoiseGateConfig dataclass
├── voice/
│   ├── gemini_live.py           # [MODIFY] Add thinking_config to LiveConnectConfig
│   │                            #          Filter thought parts in _handle_server_content
│   │                            #          Update default model_id to 2.5-series
│   ├── interruption_handler.py  # [NO CHANGE] — server-side VAD unaffected
│   └── static/                  # [NEW directory]
│       ├── noise-gate-processor.js   # [NEW] AudioWorkletProcessor module
│       └── audio_capture.js          # [NEW] Main-thread getUserMedia + AudioWorklet setup

tests/
├── unit/
│   └── test_gemini_live_thinking.py  # [NEW] ThinkingConfig in LiveConnectConfig
└── unit/
    └── test_noise_gate_math.py       # [NEW] dBFS threshold and hold timer math (Python verification)
```

**Structure Decision**: Single-project structure (Option 1). The noise gate is a static JavaScript module served by the existing server infrastructure. No new project or service boundary is introduced.

---

## Implementation Phases

### Phase A: Backend — Thinking Config + Model Update

**Files**: `src/voice/gemini_live.py`, `src/config.py`

**A1 — Add `GEMINI_MODEL_ID` to `GeminiConfig`** (`src/config.py`):
```python
@dataclass(frozen=True)
class GeminiConfig:
    api_key: Optional[str] = None
    model_id: str = "gemini-2.5-flash-preview-04-17"  # 2.5 required for thinking

    @classmethod
    def from_env(cls) -> "GeminiConfig":
        return cls(
            api_key=os.getenv("GEMINI_API_KEY"),
            model_id=os.getenv("GEMINI_MODEL_ID", "gemini-2.5-flash-preview-04-17"),
        )
```

**A2 — Add `thinking_config` to `LiveConnectConfig`** (`src/voice/gemini_live.py:334`):
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

**A3 — Use `model_id` from config** (`src/voice/gemini_live.py:211`):
```python
# Before:
model_id: str = "gemini-2.0-flash-exp"
# After: remove hardcoded default; accept from GeminiConfig
```
Propagate `self._gemini_config.model_id` to the `connect()` call.

**A4 — Filter thought parts in `_handle_server_content`** (`src/voice/gemini_live.py:582`):
```python
# Before:
if part.text:
    self._accumulated_agent_response += part.text

# After:
if part.text:
    if getattr(part, 'thought', False):
        logger.debug(f"Thought trace ({len(part.text)} chars)")
    else:
        self._accumulated_agent_response += part.text
```

**Acceptance**: `tests/unit/test_gemini_live_thinking.py`
- ThinkingConfig appears in LiveConnectConfig with correct fields
- Thought parts are not accumulated into `_accumulated_agent_response`
- Non-thought text parts continue to accumulate correctly

---

### Phase B: Client — AudioWorklet Noise Gate

**Files**: `src/voice/static/noise-gate-processor.js`, `src/voice/static/audio_capture.js`

**B1 — Create `noise-gate-processor.js`**:
Full processor as specified in `contracts/noise_gate.yaml` and `research.md R3`.
Key constants:
- `threshold = 0.003162` (verified: `10^(-50/20)`)
- `holdDurationSamples = Math.round(0.200 * sampleRate)` (computed once in constructor)

**B2 — Create `audio_capture.js`** (exported function `initNoiseGate()`):
- getUserMedia with `{ echoCancellation: true, noiseSuppression: false, autoGainControl: false }`
- Load `noise-gate-processor.js` via `audioContext.audioWorklet.addModule()`
- Build graph: `micSource → noiseGateNode → captureDestination`
- Return `{ audioContext, noiseGateNode, gatedStream, stop }`

**Acceptance**: Manual browser testing
- Silence: no audio data in gatedStream for sustained silent periods
- Speech: gatedStream carries audio within 200ms of onset
- Tab backgrounded: processing continues (verify via audio level meter or MediaRecorder bytes)
- Agent speaking through speakers: no self-triggering (echoCancellation)

---

### Phase C: Configuration + Wiring

**C1 — Add `NoiseGateConfig` to `src/config.py`** (optional; for server-side threshold documentation):
```python
@dataclass(frozen=True)
class NoiseGateConfig:
    threshold_dbfs: float = -50.0
    hold_ms: int = 200
    # float32 equivalent: 10^(threshold_dbfs/20) = 0.003162
```

**C2 — Update `WillowConfig`** to include `NoiseGateConfig` and propagate `GeminiConfig.model_id`.

---

### Phase D: Tests

**D1 — `tests/unit/test_gemini_live_thinking.py`**:
```python
def test_live_connect_config_has_thinking():
    session = StreamingSession(gemini_config=GeminiConfig(api_key="test"))
    # Inspect session._model_id and thinking_config propagation
    # Mock the client.aio.live.connect call; verify config shape

def test_thought_parts_filtered():
    # Create mock Part with thought=True; verify it does not appear in accumulated response
    # Create mock Part with thought=False; verify it does appear

def test_non_thought_text_accumulated():
    ...
```

**D2 — `tests/unit/test_noise_gate_math.py`** (Python, verifies the math is correct):
```python
import math

def test_threshold_dbfs():
    threshold = 10 ** (-50 / 20)
    assert abs(threshold - 0.003162) < 0.000001

def test_hold_samples():
    sample_rate = 48000
    hold_ms = 200
    expected = int(0.200 * sample_rate)  # 9600
    assert expected == 9600
```

---

## Risk Analysis

| Risk | Likelihood | Blast Radius | Mitigation |
|------|-----------|-------------|-----------|
| 2.5-series model not available / API key restricted | Medium | Thinking silently disabled | Document in quickstart; test with env var to confirm thinking fires |
| `part.thought` attribute not present on older SDK | Low | `getattr` with default False handles gracefully | Unit test covers this path |
| AudioWorklet CORS or HTTPS issue in dev | Medium | Noise gate init fails, voice unusable | Use `http://localhost` exception; document in quickstart |
| Implicit caching provides no measurable reduction | High | SC-002 metric unachievable | Revise SC-002 to reflect implicit-only approach; flag for ADR |

---

## ADR Suggestions

> 📋 **Architectural decision detected**: Gemini Live API does not support standard `CachedContent` caching; the only available mechanism is automatic implicit server-side caching with no user-visible signal.
> Document reasoning and tradeoffs? Run `/sp.adr live-api-caching-architecture`

> 📋 **Architectural decision detected**: Upgrading from `gemini-2.0-flash-exp` to `gemini-2.5-flash-preview` to enable thinking — this changes the model serving cost and capability profile for all sessions.
> Document reasoning and tradeoffs? Run `/sp.adr gemini-model-upgrade-2-5`

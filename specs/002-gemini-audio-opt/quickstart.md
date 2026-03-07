# Developer Quickstart: 002-gemini-audio-opt

**Voice Session Audio Quality & Cost Optimization**
**Branch**: `002-gemini-audio-opt` | **Date**: 2026-03-02

---

## What This Feature Adds

1. **Thinking-enabled Gemini Live sessions** — adds `ThinkingConfig(MINIMAL)` to session init in `src/voice/gemini_live.py`
2. **Client-side noise gate** — new `AudioWorkletProcessor` at -50 dBFS with 200ms hold
3. **Echo cancellation** — `echoCancellation: true` in getUserMedia constraints
4. **Background-proof audio processing** — AudioWorklet replaces any ScriptProcessor usage
5. **Implicit caching maximization** — keeping WebSocket connections alive (architecture already correct)

---

## Files Changed / Created

| File | Change Type | Description |
|------|------------|-------------|
| `src/voice/gemini_live.py` | Modified | Add `thinking_config` to `LiveConnectConfig`; filter thought parts in receive loop; update default model |
| `src/voice/static/noise-gate-processor.js` | New | AudioWorklet processor: -50 dBFS gate + 200ms hold |
| `src/voice/static/audio_capture.js` | New | Main-thread setup: getUserMedia → AudioWorklet → gated MediaStream |
| `src/config.py` | Modified | Add `NoiseGateConfig` and `GEMINI_MODEL_ID` env var to `GeminiConfig` |

---

## Environment Setup

No new dependencies. The noise gate is pure JavaScript; the thinking config uses the already-installed `google-genai` SDK.

Add to `.env` if testing with a 2.5-series model:

```bash
# Required for thinking support (2.0-flash-exp does NOT support thinking)
GEMINI_MODEL_ID=gemini-2.5-flash-preview-04-17
```

---

## Testing the Noise Gate

Open the browser console and run:

```javascript
// Initialize and observe gate state
const { gatedStream, stop } = await initNoiseGate();
const track = gatedStream.getAudioTracks()[0];
console.log('Gated track active:', track.enabled);

// Speak: gated stream should carry audio
// Stay silent for >200ms: gated stream should produce silence

// Clean up
stop();
```

Verify:
- With silence: no audio packets consumed by Gemini Live stream
- With speech: audio passes through within 200ms of speech onset
- With browser tab backgrounded: processing continues (check via audio level meter)

---

## Testing the Thinking Config

```python
import asyncio
from src.voice.gemini_live import StreamingSession
from src.config import GeminiConfig

async def test_thinking():
    session = StreamingSession(
        gemini_config=GeminiConfig(api_key="your-key"),
        model_id="gemini-2.5-flash-preview-04-17"  # must be 2.5-series
    )
    await session.connect()
    print("Connected. Thinking config active.")
    # Check response parts for thought=True parts in receive loop
    await session.disconnect()

asyncio.run(test_thinking())
```

Verify: Response parts with `part.thought == True` appear in logs (from `include_thoughts=True`). These should NOT appear in the surface text response shown to the user.

---

## Constitution Compliance Check

| Principle | Compliance |
|-----------|-----------|
| Tier 1 <50ms | Noise gate does not affect server-side tiers — ✅ |
| Tier 2 <5ms | ThinkingConfig is session init, not per-turn — ✅ |
| Tier 4 latency masked by Human Filler | MINIMAL thinking level minimizes additional latency — ✅ |
| ±2.0 state change cap | Not affected by this feature — ✅ |
| Voice I/O: Gemini Live API | This feature enhances (not replaces) the Live API integration — ✅ |

---

## Known Limitations

- **ThinkingLevel.MINIMAL** silently does nothing on `gemini-2.0-flash-exp` — must use 2.5-series model
- **Implicit caching** provides automatic cost reduction but cannot be measured or configured
- **SC-002** (≥80% cost reduction for long sessions) is not achievable via explicit caching in Live API; metric should be revised or architecture evolved (see `/sp.adr live-api-caching-architecture`)
- **AudioWorklet** requires HTTPS in production; local development on `http://localhost` typically works

# Willow Architecture

## Four-Tier Processing Pipeline

```
User Input
   │
   ▼
Tier 1: Reflex (<50ms)
   │  Tone detection, Warm but Sharp opener selection
   │  Runs on every token — immediate tone mirroring
   ▼
Tier 2: Metabolism (<5ms)
   │  State formula: aₙ₊₁ = aₙ + d + m
   │  Applies ±2.0 cap, Cold Start (d=0 turns 1-3)
   │  Updates SessionState atomically via asyncio.Lock
   ▼
Tier 3: Conscious (<500ms)  [background asyncio.Task]
   │  ThoughtSignature: Intent/Tone separation (Principle II)
   │  TacticDetector: soothing, mirroring, gaslighting, deflection, contextual_sarcasm
   │  Sincere Pivot detection (Grace Boost path)
   ▼
Tier 4: Sovereign (<2s)  [background asyncio.Task — on-demand]
   │  Three-gate check: confidence → keyword match → Tier 3 intent
   │  Hard exit: task.cancel() on active Gemini coroutine
   │  Response from data/sovereign_truths.json — zero LLM involvement
   │  Synthetic turn injection (FR-008e)
   └── Flush AudioWorklet on fire (T025)
```

## State Formula

```
aₙ₊₁ = aₙ + d + m

aₙ = current_m (behavioral state, float)
d  = base_decay
     = 0.0  during Cold Start (turns 1-3)
     = -0.1 after turn 3
m  = feedback modifier, capped at ±2.0

Cold Start: first 3 turns — d=0, no penalties (Social Handshake)
```

## Behavioral Zones

| Zone | current_m | Persona Response |
|------|-----------|-----------------|
| High | > 0.5 | Warm openers, analogies every 3rd turn, wit |
| Neutral | -0.5 to 0.5 | Professional, balanced, no hedging |
| Low | < -0.5 | Concise, direct, 1-2 sentences, formal |

## Sovereign Truth System

Sovereign Truths are deterministic facts stored in `data/sovereign_truths.json`. They **never** enter the LLM context window (FR-007).

Three-gate check before firing:
1. Transcription confidence ≥ threshold (gate 1)
2. ≥2 keyword matches OR residual plot weighted average < 0 (gate 2)
3. Tier 3 intent = "contradicting" at 0.85+ confidence (gate 3)

## Audio Pipeline (spec 002)

```
Browser                          Python
───────────────────────────────────────────────────
getUserMedia (mic)
  → noise-gate-processor.js     ← configurable threshold (T024)
    [adaptive buffer: 1024→512] ← 30s stable → halve latency (T026)
    [3s preflight warmup]       → {"type":"preflight_start/end"} (T028)
  → WebSocket (binary audio)
                                → WillowAgent.voice_stream_handler()
Tier 4 fires                    → {"type":"flush_audio_buffer"}
  → handleServerCommand()
    → noiseGateNode.port.postMessage({type:"flush"})
      → 7ms linear fade-out
```

## Troll Defense

After 3 consecutive Sovereign Spikes (`is_sovereign_spike=True`):
1. `troll_defense_active = True` in SessionState
2. `process_turn()` returns boundary statement (T045)
3. Tier 1/3/4 are skipped; Tier 2 still runs (turn count advances)
4. Troll Defense resets via `reset_troll_defense()` when tone changes

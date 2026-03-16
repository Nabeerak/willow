# <img src="../Gemini_Generated_Image_jhw85ejhw85ejhw8.png" width="100" height="100" align="right" /> Willow Architecture

## System Overview

```mermaid
flowchart TD
    MIC["🎤 Browser Microphone\n(getUserMedia)"]
    NGP["noise-gate-processor.js\nAdaptive buffer 1024→512\n3s preflight warmup"]
    WS["WebSocket\nbinary audio + JSON control"]
    AGENT["WillowAgent (src/main.py)\nSession orchestration"]

    T1["Tier 1: Reflex  &lt;50ms\nTone mirroring, Warm but Sharp"]
    T2["Tier 2: Metabolism  &lt;5ms\naₙ₊₁ = aₙ + d + m"]
    T3["Tier 3: Conscious  &lt;500ms\nThoughtSignature + TacticDetector"]
    T4["Tier 4: Sovereign  &lt;2s\nDeterministic truth override"]

    GEMINI["☁️ Gemini Live API\ngoogle-genai BidiGenerateContent\ngemini-2.5-flash-native-audio-preview"]
    ST["data/sovereign_truths.json\n(zero LLM involvement)"]

    AUDIO_OUT["🔊 Audio Output\nPCM stream back to browser"]
    FILLER["Filler Audio Player\nhmm.wav / aah.wav (≥200ms mask)"]

    MIC --> NGP --> WS --> AGENT
    AGENT --> T1 --> T2 --> T3 --> T4
    T3 -- "streaming turns" --> GEMINI
    GEMINI -- "PCM audio + transcript" --> AUDIO_OUT
    T4 -- "override: cancel Gemini coroutine" --> GEMINI
    T4 -- "lookup" --> ST
    T3 -- "latency > 200ms" --> FILLER
    T4 -- "latency > 200ms" --> FILLER
    AGENT -- "flush_audio_buffer cmd" --> NGP
```

## Four-Tier Processing Pipeline

![Willow Architecture Diagram](architecture.svg)

Gemini Live API (☁️ google-genai BidiGenerateContent)
   │  Model: gemini-2.5-flash-native-audio-preview-12-2025
   │  Bidirectional: sends audio → receives PCM audio + transcript
   │  Cancelled by Tier 4 when Sovereign Truth fires
   └── PCM audio streamed back to browser via WebSocket
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

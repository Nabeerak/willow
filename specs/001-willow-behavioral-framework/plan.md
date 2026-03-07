# Implementation Plan: Willow Behavioral Framework

**Branch**: `001-willow-behavioral-framework` | **Date**: 2026-02-28 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-willow-behavioral-framework/spec.md`

**Note**: This template is filled in by the `/sp.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Willow is a real-time voice agent that implements a Behavioral Framework based on six core principles (Memory, Intuition, Integrity, Mood, Self-Respect, Sovereignty). The system maintains conversational state through a Residual Plot (rolling 5-turn history), detects psychological tactics via Thought Signatures, and enforces behavioral boundaries through a multi-tier architecture. Primary technical challenge: maintaining sub-2s response latency while processing complex behavioral analysis across 4 asynchronous tiers.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: Google ADK (Agent Development Kit), Gemini Live API SDK, dataclasses (state management)
**Storage**: In-memory session state (Residual Plot, m values), Sovereign Truth hard override layer (structured JSON with response_template fields, top 10 cached, three-gate contradiction detection before prompt construction, zero tokens consumed), cloud logging for Thought Signatures
**Testing**: pytest (unit/integration), Calibration Cohort scenarios (Blunt Friend, Polite Friend, Chaos Friend, Soft-Spoken Friend personas) — includes template voice review step
**Target Platform**: Google Cloud Run (serverless deployment), voice I/O via Gemini Live API
**Project Type**: Single project (voice agent service)
**Performance Goals**: Tier 1 <50ms (token generation), Tier 2 <5ms (behavioral math), Tier 3 <500ms (tactic detection), Tier 4 <2s (Sovereign Truth lookup)
**Constraints**: Real-time voice latency <2s total response time, 95% of Tier 3/4 delays masked by filler audio, single-session memory only (no persistence)
**Scale/Scope**: Gemini Live Agent Challenge hackathon demo (March 2026), single concurrent user per session, 10+ turn conversations

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Core Principle Compliance

✅ **I. Memory (The Sequence)**
- Residual Plot implementation: Rolling 5-turn array with recency weights (0.40, 0.25, 0.15, 0.12, 0.08)
- Decay Formula: `aₙ₊₁ = aₙ + d + m` implemented in Tier 2
- Cold Start: `d=0` for first 3 turns enforced

✅ **II. Intuition (The Signature)**
- Tone vs. Intent separation: Dual-stream processing in Tier 3
- Tactic Detection: 5 minimum types (Soothing, Mirroring, Gaslighting, Deflection, Contextual Sarcasm)
- Sarcasm vs. Malice Rule: Residual Plot check before classification

✅ **III. Integrity (The Anchor)**
- Zero-Token Architecture: Sovereign Truths NEVER enter the LLM context window under any condition — not when contradicted, not on any turn. They live in JSON cache exclusively. Programmatic responses injected directly into audio pipeline (FR-007)
- Hard Override Layer: SovereignTruthCache intercepts user input before prompt is built — synchronous local dictionary lookup only, zero network calls (FR-008)
- Three-Gate Check: (1) 2-keyword match minimum, (2) transcription confidence threshold, (3) Tier 3 intent = `contradicting` @ 0.85 confidence as parallel pre-check with 1.5s cutoff (FR-008c, FR-008d, FR-022)
- Input Normalization: lowercase → strip punctuation → lemmatize → interrogative structure detection with reduced confidence weight for question-form inputs (FR-008f)
- Templates as Data: `response_template` fields in `sovereign_truths.json`, persona-calibrated Warm but Sharp voice, reviewed in Calibration Cohort — NOT hardcoded Python strings (FR-008h)
- Tier 4 Hard Exit: `task.cancel()` on active Gemini coroutine + return guard before response construction (FR-008g)
- Synthetic Turn Injection: f-string with exact verbatim assertion values appended to conversation history after every Tier 4 response (FR-008e)
- `audio_started` Flag: permanently blocks Tier 4 firing once audio streaming begins on a turn (FR-022)
- Security: `sovereign_truths.json` read-only at startup, hash validation against Google Cloud Secret Manager, automated hash rotation in `cloudbuild.yaml` (FR-008i, FR-008j)
- Cold Start Deferral: contradictions in turns 1-3 queued, evaluated at turn 4 with relevance check (FR-020, FR-021)
- Echo Leakage: 200ms interruption cooldown after agent audio ends (FR-023)
- Assertion Caching: Top 10 Sovereign Truths cached in memory for zero-latency deterministic lookup (FR-008b)
- MVP Decision: JSON keyword lookup chosen over vector embedding — fast, deterministic, zero hallucination risk; vector embedding deferred (FR-008a)
- No Wheeling: Plot boundaries enforced

✅ **IV. Mood (The Pulse)**
- Arithmetic Sequence: Implemented for Social Presence (MVP)
- Exponential/Sine Wave: Deferred per constitution (MVP scope)
- Priority Logic: Arithmetic baseline only (simplified for MVP)

✅ **V. Self-Respect (The Dignity Floor)**
- ±2.0 State Change Cap: Enforced per turn
- Sovereign Spike: `m = -(decay_rate + 5.0)` on devaluing intent
- Troll Defense: 3 consecutive spikes trigger boundary statement
- Forgiveness Trigger: +2.0 Grace Boost on Sincere Pivot

✅ **VI. Sovereignty (The Owned Plot)**
- Plot Priority: User contradictions trigger Tier 4
- Curation Responsibility: Manual curation required for demo fact set
- Wheeling Boundaries: Agent constrained within Plot domain

### Architecture Compliance

✅ **4-Tier Asynchronous Architecture**
- Tier 1: Reflex (every token, <50ms) — tone mirroring
- Tier 2: Metabolism (every turn, <5ms) — behavioral state math
- Tier 3: Conscious (every 2-3 turns, <500ms) — Thought Signature analysis
- Tier 4: Sovereign (on-demand, <2s) — deterministic contradiction detection triggers programmatic response construction in Python (bypasses LLM generation)

✅ **Human Filler**: Natural audio clips mapped to tier triggers

✅ **Tech Stack**: Gemini Live API, Google ADK, Cloud Run, Python dataclass, Cloud Logging, Google Cloud Secret Manager

### MVP Scope Compliance

✅ All 10 MVP features from constitution checklist addressed in spec
✅ Deferred features (Exponential/Sine, full Plot DB, multi-session) documented

**Gate Result**: PASS — All constitutional requirements met or appropriately scoped for MVP

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/sp.plan command output)
├── research.md          # Phase 0 output (/sp.plan command)
├── data-model.md        # Phase 1 output (/sp.plan command)
├── quickstart.md        # Phase 1 output (/sp.plan command)
├── contracts/           # Phase 1 output (/sp.plan command)
└── tasks.md             # Phase 2 output (/sp.tasks command - NOT created by /sp.plan)
```

### Source Code (repository root)

```text
src/
├── core/
│   ├── state_manager.py          # Behavioral state (m, d), Residual Plot
│   ├── residual_plot.py           # Rolling 5-turn array with weights
│   └── sovereign_truth.py         # Hard override layer: deterministic contradiction detection + Owned Plot cache (top 10 truths)
├── tiers/
│   ├── tier1_reflex.py            # Tone mirroring (<50ms)
│   ├── tier2_metabolism.py        # State transitions (<5ms)
│   ├── tier3_conscious.py         # Thought Signature analysis (<500ms)
│   └── tier4_sovereign.py         # Programmatic response from response_template, task.cancel(), synthetic turn injection (<2s)
├── signatures/
│   ├── thought_signature.py       # Intent/Tone separation
│   ├── tactic_detector.py         # 5 tactic types
│   └── parser.py                  # [THOUGHT] tag system
├── voice/
│   ├── gemini_live.py             # Gemini Live API integration
│   ├── filler_audio.py            # Human filler clips mapper
│   └── interruption_handler.py    # Real-time interruption support
├── persona/
│   └── warm_sharp.py              # Sovereign Consultant persona logic
├── main.py                        # Agent orchestration entry point
└── config.py                      # Environment config, latency budgets

tests/
├── cohort/
│   ├── test_blunt_friend.py       # Blunt persona scenarios
│   ├── test_polite_friend.py      # Polite persona scenarios
│   └── test_chaos_friend.py       # Chaos persona scenarios
├── integration/
│   ├── test_voice_flow.py         # End-to-end voice conversation
│   ├── test_behavioral_state.py   # State transitions across turns
│   └── test_tactic_detection.py   # Tactic flagging accuracy
└── unit/
    ├── test_residual_plot.py      # 5-turn rolling array
    ├── test_state_manager.py      # m/d calculations
    └── test_thought_signature.py  # Intent/Tone separation

data/
├── sovereign_truths.json          # Curated fact set with response_template fields (read-only, hash-validated at startup)
└── filler_audio/
    ├── hmm.wav                    # Tier 3 filler
    ├── aah.wav                    # Tier 4 filler
    ├── right_so.wav
    ├── interesting.wav
    └── cool_but.wav

.env.example                       # Gemini API key template
requirements.txt                   # Python dependencies
cloudbuild.yaml                    # Google Cloud Run deployment
README.md                          # Setup and quickstart
```

**Structure Decision**: Single project structure selected. Voice agent service with modular tier separation for maintainability and latency monitoring. Core behavioral logic separated from voice I/O to enable future multi-modal support (text, video) without tier refactoring.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No constitutional violations detected. All complexity justified by constitutional requirements:

- **4-Tier Architecture**: Required by constitution (Asynchronous Tiered Architecture with latency budgets)
- **Multi-Stream Processing**: Required by Intuition principle (Tone vs. Intent separation)
- **State Management Complexity**: Required by Memory principle (Residual Plot with weighted decay)
- **Hard Override Layer**: Required by Integrity principle (deterministic Sovereign Truth interception before prompt construction — JSON lookup for MVP, vector embedding deferred)

All implementation choices align with constitutional mandates and MVP scope.

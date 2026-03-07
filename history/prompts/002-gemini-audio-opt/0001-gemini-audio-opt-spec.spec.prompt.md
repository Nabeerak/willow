---
id: "0001"
title: Gemini Audio Optimization Spec
stage: spec
date: 2026-03-01
surface: agent
model: claude-sonnet-4-6
feature: 002-gemini-audio-opt
branch: 002-gemini-audio-opt
user: nabeera
command: /sp.specify
labels: ["voice", "gemini-live", "noise-gate", "vad", "context-caching", "audio-worklet", "cost-optimization"]
links:
  spec: specs/002-gemini-audio-opt/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - specs/002-gemini-audio-opt/spec.md
  - specs/002-gemini-audio-opt/checklists/requirements.md
  - history/prompts/002-gemini-audio-opt/0001-gemini-audio-opt-spec.spec.prompt.md
tests:
  - "none"
---

## Prompt

The Gemini Live API should be configured with thinking_level: MINIMAL and include_thoughts: true to avoid multi-model switching latency while retaining on-demand reasoning capability for complex turns.
A client-side noise gate using RMS volume detection at -50dB threshold prevents background noise and silence from consuming audio tokens at the 32 tokens/second billing rate. A 200ms hold/release prevents gate jitter during natural speech pauses.
echoCancellation: true must be set in getUserMedia constraints to prevent the agent's own voice from triggering the noise gate and creating a feedback loop.
VAD (Voice Activity Detection) should close the audio stream during silence to avoid billing silent tokens. This pairs with the existing interruption handler in src/voice/interruption_handler.py.
Context Caching should be implemented for sessions exceeding 10 minutes to reduce token costs by up to 90% on long-running conversations.
AudioWorklet should be used instead of the deprecated ScriptProcessor to ensure the noise gate continues functioning when the browser tab is backgrounded or loses focus.
The thinking_config JSON parameters should be included in the Gemini Live API session initialization in src/voice/gemini_live.py from the start of implementation to avoid retrofitting later.

## Response snapshot

Created feature branch `002-gemini-audio-opt` and wrote spec at `specs/002-gemini-audio-opt/spec.md`. Specification covers 5 user stories (P1-P5): clean voice input without echo/noise, no billing for silence, responsive agent on complex questions, affordable long conversations via context caching, and continued audio processing when tab is backgrounded. All 8 functional requirements defined; all 6 success criteria are measurable and technology-agnostic. Assumptions section documents RMS threshold derivation and integration points. Quality checklist passed with zero failing items.

## Outcome

- ✅ Impact: Spec establishes clear user-facing requirements for voice cost optimization and audio quality; ready for planning phase
- 🧪 Tests: No tests run (spec phase)
- 📁 Files: specs/002-gemini-audio-opt/spec.md, specs/002-gemini-audio-opt/checklists/requirements.md
- 🔁 Next prompts: `/sp.clarify` to refine edge cases or `/sp.plan` to proceed to architecture
- 🧠 Reflection: Feature description was highly technical; spec successfully abstracted to user-value language while preserving all behavioral constraints. FR-007 (VAD + interruption handler coordination) flagged in checklist notes as a planning-phase concern.

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): quality checklist — all items PASS
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): run /sp.clarify to surface any remaining ambiguity before planning

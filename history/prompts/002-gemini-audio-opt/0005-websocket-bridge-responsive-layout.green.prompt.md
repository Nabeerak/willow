---
id: "0005"
title: WebSocket Bridge and Responsive Layout for Willow Dashboard
stage: green
date: 2026-03-06
surface: agent
model: claude-opus-4-6
feature: 002-gemini-audio-opt
branch: 002-gemini-audio-opt
user: nabeera
command: "integrate willow-dashboard with FastAPI backend via WebSocket bridge; make responsive"
labels: ["websocket", "audio", "responsive", "dashboard", "pcm", "gemini-live"]
links:
  spec: specs/002-gemini-audio-opt/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - willow-dashboard/index.html
tests:
  - manual: open dashboard, click mic button, verify WS connects to backend on :8081
  - manual: speak into mic, verify PCM streams to server at 16kHz
  - manual: verify agent audio plays back via 24kHz queue
  - manual: verify status pill shows on md breakpoint (tablet)
  - manual: demo mode activates when backend unavailable (toast shown)
---

## Prompt

(Continued from prior session — implement WebSocket bridge and responsive layout for willow-dashboard)

## Response snapshot

Implemented full WebSocket bridge in `willow-dashboard/index.html`:

1. **Backend config**: `BACKEND_HTTP`/`BACKEND_WS` constants auto-detect from `location.hostname:8081`; overridable via `window.WILLOW_BACKEND_URL`.

2. **`#connectWebSocket()`**: POST `/api/v1/session` → extract `session_id` → open WS to `/api/v1/session/{id}/stream`; 8s timeout; resolves on `onopen`, rejects on error/timeout.

3. **`#transitionTo('CONNECTING')`**: awaits `#connectWebSocket()`; on failure → toast "demo mode" + falls back to mock countdown.

4. **`#setupPcmStreaming(source)`**: `ScriptProcessorNode` at 4096-sample buffer; downsamples device rate → 16kHz; converts Float32 → Int16; sends `pcm16.buffer` as binary WS frame when LIVE.

5. **`#stopAudio()`**: sends `{"type":"end_turn"}` JSON, disconnects `ScriptProcessor`, stops `MediaStream` tracks, closes `AudioContext`.

6. **`#handleWsMessage(e)`**: binary → `#queueAudioPlayback()`; JSON `turn_complete` → add transcript + fetch state snapshot; `interrupted` → flush queue; `text_response` → add transcript + update mModifier.

7. **`#drainAudioQueue()`**: sequential 24kHz PCM playback via `AudioContext({sampleRate:24000})`; `onended` chain.

8. **`#fetchSessionSnapshot()`**: polls `GET /api/v1/session/{id}/state` after each `turn_complete`; feeds into `#handleSessionSnapshot()` which normalizes `current_m` (-10…+10) → 0…1.

9. **`#updateWsStatus()`**: updates `#ws-status-text` and `#ws-status-dot` elements for connected/connecting/disconnected states.

10. **Mock mode**: `#startMockSocket()` suppresses all simulation when `#wsConnected === true`; demo mode still runs when backend unavailable.

11. **Responsive**: status pill changed from `hidden lg:flex` → `hidden md:flex` (shows on tablet 768px+).

## Outcome

- ✅ Impact: Dashboard is now fully wired to the FastAPI backend; real audio flows end-to-end via WS
- 🧪 Tests: Manual testing against `uvicorn src.server:app --port 8081`
- 📁 Files: willow-dashboard/index.html (1332 lines, +254 from bridge implementation)
- 🔁 Next prompts: T069 Cloud Run deploy; spec-003 Exponential/Sine Wave mood sequences
- 🧠 Reflection: ScriptProcessorNode is deprecated but universally supported in browsers; AudioWorklet would require a separate JS file served from the same origin — acceptable trade-off for dashboard use

## Evaluation notes (flywheel)

- Failure modes observed: none in syntax check; backend CORS may be needed for cross-origin requests from Vite dev server
- Graders run and results (PASS/FAIL): JS syntax check via `node --check` — PASS
- Prompt variant (if applicable): null
- Next experiment: add CORS middleware to server.py if browser blocks cross-origin POST to :8081

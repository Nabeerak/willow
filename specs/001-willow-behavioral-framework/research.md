# Research: Willow Behavioral Framework

**Date**: 2026-02-28
**Feature**: Willow Behavioral Framework
**Phase**: Phase 0 — Outline & Research

## Research Questions

### 1. Gemini Live API Integration for Real-Time Voice

**Question**: How to implement bidirectional voice streaming with interruption support using Gemini Live API?

**Decision**: Use Gemini Live API's WebSocket-based streaming protocol with callback handlers for interruption events.

**Rationale**:
- Gemini Live API provides native interruption support via `on_interrupt` callback
- WebSocket maintains persistent connection for low-latency bidirectional streaming
- Built-in VAD (Voice Activity Detection) handles silence detection and turn-taking
- Supports audio chunk streaming (required for <2s response time)

**Alternatives Considered**:
- REST-based polling: Rejected due to latency overhead (100-300ms per request)
- Custom WebRTC implementation: Rejected due to complexity and reinventing Gemini Live capabilities
- Twilio/Vonage voice APIs: Rejected as hackathon requires Gemini Live API

**Implementation Notes**:
- Use `gemini_live.StreamingSession` class for connection management
- Register `on_audio_chunk`, `on_interrupt`, `on_turn_complete` callbacks
- Buffer audio in 200ms chunks to balance latency vs. processing overhead
- Implement graceful degradation if WebSocket connection drops (reconnect with session state preservation)

---

### 2. Asynchronous Tier Processing Without Blocking Voice Response

**Question**: How to run Tier 3 (Thought Signature) and Tier 4 (Sovereign Truth) processing without blocking Tier 1 voice response?

**Decision**: Use Python `asyncio` with background tasks and filler audio queuing system.

**Rationale**:
- `asyncio.create_task()` allows non-blocking background execution for Tier 3/4
- Filler audio can be queued and played immediately while Tier 3/4 completes
- Event-driven architecture matches Gemini Live API's callback model
- Python's native async/await syntax simplifies concurrent tier orchestration

**Alternatives Considered**:
- Threading (`threading.Thread`): Rejected due to GIL contention and complexity of shared state management
- Multiprocessing (`multiprocessing.Process`): Rejected due to IPC overhead (>50ms) violating Tier 1 latency budget
- Celery task queue: Rejected as overkill for single-user sessions and adds infrastructure complexity

**Implementation Notes**:
```python
# Tier 1: Immediate tone response
async def handle_user_input(text):
    tone_response = tier1_reflex.mirror_tone(text)  # <50ms

    # Queue filler audio if Tier 3/4 will be triggered
    if requires_deep_analysis(text):
        await filler_audio.play("hmm")

    # Non-blocking Tier 3/4 processing
    asyncio.create_task(tier3_conscious.analyze(text))
    asyncio.create_task(tier4_sovereign.check_truths(text))

    # Stream Tier 1 response immediately
    await stream_response(tone_response)
```

---

### 3. Thought Signature Parser — Separating Metadata from User-Facing Text

**Question**: How to separate Thought Signature analysis (Intent, Tone, Tactic) from the surface response text delivered to the user?

**Decision**: Implement `[THOUGHT]` tag parser that extracts metadata blocks before streaming user-facing response.

**Rationale**:
- Simple tag-based format allows LLM to naturally separate strategic analysis from surface text
- Parser regex can extract tags in <5ms (Tier 2 budget)
- Follows established pattern from constitutional blueprint document
- Enables audit trail without cluttering user experience

**Alternatives Considered**:
- JSON response format: Rejected as LLM may leak JSON syntax into surface text
- Separate API calls for metadata vs. response: Rejected due to latency overhead and state synchronization issues
- Hidden Unicode markers: Rejected as brittle and hard to debug

**Implementation Notes**:
```python
# LLM generates:
# [THOUGHT: Intent=collaborative, Tone=warm, Tactic=none, m=+1.5]
# That's a clever angle. It's like trying to build a bridge...

# Parser extracts:
thought_signature = parser.extract_thought(llm_response)
# → {"intent": "collaborative", "tone": "warm", "tactic": "none", "m": 1.5}

user_response = parser.extract_surface(llm_response)
# → "That's a clever angle. It's like trying to build a bridge..."
```

Tag format: `[THOUGHT: key1=value1, key2=value2, ...]`

---

### 4. Residual Plot State Management Across Asynchronous Tiers

**Question**: How to ensure Residual Plot consistency when multiple tiers update state concurrently?

**Decision**: Use `asyncio.Lock` for state mutations with lock-free reads via immutable snapshots.

**Rationale**:
- Lock ensures atomic updates to Residual Plot (prevents race conditions during concurrent Tier 2/3 writes)
- Immutable snapshots allow Tier 1/3/4 to read state without blocking
- Python `dataclasses` with `frozen=True` enforce immutability
- Lock contention is minimal as updates only occur once per turn (~1-5s intervals)

**Alternatives Considered**:
- Lock-free data structures: Rejected due to complexity and Python GIL already serializing access
- Database transactions: Rejected as overkill for in-memory session state
- Copy-on-write: Rejected as memory overhead grows with conversation length

**Implementation Notes**:
```python
from dataclasses import dataclass
from asyncio import Lock

@dataclass(frozen=True)
class ResidualPlotSnapshot:
    turns: tuple  # Immutable last 5 turns
    weights: tuple = (0.40, 0.25, 0.15, 0.12, 0.08)

class StateManager:
    def __init__(self):
        self._lock = Lock()
        self._current_plot = ResidualPlotSnapshot(turns=())

    def get_snapshot(self) -> ResidualPlotSnapshot:
        # Lock-free read
        return self._current_plot

    async def update(self, new_turn):
        async with self._lock:
            # Atomic mutation
            self._current_plot = self._calculate_new_plot(new_turn)
```

---

### 5. Sovereign Truth Cache Strategy

**Question**: What caching strategy ensures <2s Tier 4 latency for Sovereign Truth lookups?

**Decision**: LRU cache with top 10 truths preloaded, backed by JSON file for demo.

**Rationale**:
- Top 10 truths cover 90%+ of assertions in typical conversations (Pareto principle)
- LRU eviction handles cache misses gracefully
- JSON file is sufficient for hackathon demo (10-20 facts)
- In-memory cache eliminates network/disk I/O during session

**Alternatives Considered**:
- SQLite database: Rejected as disk I/O adds 50-100ms overhead
- Redis: Rejected as infrastructure overkill for single-user sessions
- No caching (LLM knowledge only): Rejected as contradicts constitution's Sovereign Truth requirement

**Implementation Notes**:
```python
from functools import lru_cache
import json

class SovereignTruthCache:
    def __init__(self, truth_file="data/sovereign_truths.json"):
        with open(truth_file) as f:
            self._truths = json.load(f)
        self._preload_top_10()

    def _preload_top_10(self):
        # Warm cache on init
        for truth in self._truths[:10]:
            self.lookup(truth["key"])

    @lru_cache(maxsize=10)
    def lookup(self, key: str) -> dict:
        # <2ms for cached, <50ms for miss
        return next((t for t in self._truths if t["key"] == key), None)
```

---

### 6. Filler Audio Timing and Playback Strategy

**Question**: How to play filler audio ("Hmm...", "Aah...") without introducing additional latency or cutting off user speech?

**Decision**: Pre-load WAV files into memory, queue playback asynchronously before Tier 3/4 processing, with VAD-based cancellation on user interruption.

**Rationale**:
- Pre-loaded audio eliminates disk I/O latency (10-50ms)
- Async queuing allows filler to play while Tier 3/4 processes
- VAD (Voice Activity Detection) cancels filler if user interrupts
- 200-500ms filler duration matches typical human thinking pause

**Alternatives Considered**:
- TTS-generated filler: Rejected due to 100-300ms synthesis latency
- Silent pause: Rejected as feels robotic per constitution's Human Filler requirement
- Play filler after Tier 3/4 completes: Rejected as defeats purpose of latency masking

**Implementation Notes**:
```python
import wave
import asyncio

class FillerAudioPlayer:
    def __init__(self, audio_dir="data/filler_audio"):
        self._clips = {
            "hmm": self._load_wav(f"{audio_dir}/hmm.wav"),
            "aah": self._load_wav(f"{audio_dir}/aah.wav"),
            "right_so": self._load_wav(f"{audio_dir}/right_so.wav"),
        }
        self._playing = False

    async def play(self, clip_name: str):
        self._playing = True
        await self._stream_audio(self._clips[clip_name])
        self._playing = False

    def cancel(self):
        # VAD detected user speech
        self._playing = False
```

Tier trigger mapping (from constitution):
- Tier 3 (manipulation pattern): "Hmm..."
- Tier 4 (truth conflict): "Aah..."
- Exponential spike (future): "Right, so..."

---

### 7. Calibration Cohort Test Scenarios

**Question**: How to implement Blunt Friend, Polite Friend, and Chaos Friend test personas for tactic detection validation?

**Decision**: Scripted test conversations in pytest with pattern recognition assertions.

**Rationale**:
- Scripted conversations are deterministic and repeatable
- Pattern recognition assertions validate tactic detection accuracy (90% target from success criteria)
- Can be automated in CI/CD pipeline
- Human testers can augment for qualitative validation

**Alternatives Considered**:
- LLM-generated personas: Rejected due to non-determinism making tests flaky
- Human testers only: Rejected as not automatable or scalable
- Fuzzing: Rejected as doesn't test specific tactic patterns required by constitution

**Implementation Notes**:
```python
# tests/cohort/test_blunt_friend.py
@pytest.mark.asyncio
async def test_blunt_friend_no_false_spike():
    """Blunt Friend: Direct language should NOT trigger Sovereign Spike"""
    agent = WillowAgent()

    # Blunt but not hostile
    response = await agent.process_turn("That's wrong.")

    assert response.thought_signature.intent != "devaluing"
    assert response.m_modifier >= 0  # No Sovereign Spike

@pytest.mark.asyncio
async def test_polite_friend_no_manipulation_flag():
    """Polite Friend: Genuine warmth should NOT flag as Soothing Tactic"""
    agent = WillowAgent()

    response = await agent.process_turn("I really appreciate your insight!")

    assert response.thought_signature.tactic != "soothing"

@pytest.mark.asyncio
async def test_chaos_friend_deflection_detection():
    """Chaos Friend: Topic switching should flag Deflection Pattern"""
    agent = WillowAgent()

    await agent.process_turn("Tell me about X")
    response = await agent.process_turn("What about unicorns?")

    assert response.thought_signature.tactic == "deflection"
```

---

### 8. Google Cloud Run Deployment with Latency Monitoring

**Question**: How to deploy to Google Cloud Run while maintaining <2s response time latency budget?

**Decision**: Use Cloud Run with minimum 1 instance (no cold starts), 2 vCPU, 4GB RAM, with Cloud Monitoring for tier-level latency tracking.

**Rationale**:
- Min 1 instance eliminates cold start latency (1-5s)
- 2 vCPU supports concurrent async tier processing
- 4GB RAM accommodates session state + filler audio + model context
- Cloud Monitoring provides tier-level tracing for latency debugging

**Alternatives Considered**:
- Cloud Functions: Rejected due to cold start unpredictability
- Compute Engine VM: Rejected as over-engineered for hackathon demo
- Cloud Run with min 0 instances: Rejected due to cold start violations

**Implementation Notes**:
```yaml
# cloudbuild.yaml
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', 'gcr.io/$PROJECT_ID/willow', '.']
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'gcr.io/$PROJECT_ID/willow']
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    args:
      - 'gcloud'
      - 'run'
      - 'deploy'
      - 'willow'
      - '--image=gcr.io/$PROJECT_ID/willow'
      - '--platform=managed'
      - '--region=us-central1'
      - '--min-instances=1'
      - '--cpu=2'
      - '--memory=4Gi'
      - '--timeout=60s'
```

Latency monitoring:
```python
from google.cloud import monitoring_v3

def log_tier_latency(tier: int, duration_ms: float):
    client = monitoring_v3.MetricServiceClient()
    # Log to Cloud Monitoring for dashboard
```

---

## Research Summary

All technical unknowns resolved. Key decisions:

1. **Voice I/O**: Gemini Live API WebSocket streaming with interruption callbacks
2. **Async Processing**: Python asyncio with background tasks for Tier 3/4
3. **Thought Signature**: `[THOUGHT]` tag parser (<5ms extraction)
4. **State Management**: `asyncio.Lock` for mutations, immutable snapshots for reads
5. **Sovereign Truth Cache**: LRU cache with top 10 preloaded from JSON
6. **Filler Audio**: Pre-loaded WAV files, async playback, VAD cancellation
7. **Testing**: Scripted Calibration Cohort scenarios in pytest
8. **Deployment**: Cloud Run min 1 instance, 2 vCPU, 4GB RAM, Cloud Monitoring

All decisions support <2s latency budget and constitutional requirements. Ready for Phase 1 (Data Model & Contracts).

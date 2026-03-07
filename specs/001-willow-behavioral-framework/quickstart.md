# Quickstart: Willow Behavioral Framework

**Feature**: Willow Behavioral Framework
**Date**: 2026-02-28
**Purpose**: Step-by-step guide to run Willow locally and verify core functionality

## Prerequisites

- Python 3.11+
- Gemini Live API key (from Google AI Studio)
- Google Cloud Project with Cloud Run enabled
- 4GB available RAM
- Microphone and speakers for voice testing

## Setup

### 1. Clone and Install Dependencies

```bash
git clone https://github.com/nabeera/willow.git
cd willow
git checkout 001-willow-behavioral-framework

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env and add your Gemini Live API key
```

`.env` contents:
```
GEMINI_API_KEY=your_api_key_here
SESSION_TIMEOUT_SECONDS=3600
MIN_FILLER_LATENCY_MS=200
ENABLE_CLOUD_LOGGING=false  # Set true for production
```

### 3. Verify Filler Audio Files

```bash
ls -lh data/filler_audio/
# Should show: hmm.wav, aah.wav, right_so.wav, interesting.wav, cool_but.wav
```

If files missing, run:
```bash
python scripts/generate_filler_audio.py
```

### 4. Load Sovereign Truths

```bash
cat data/sovereign_truths.json
# Verify 10+ curated facts exist
```

## Run Locally

### Option 1: Interactive Voice Session

```bash
python src/main.py --mode voice

# Output:
# 🎙️  Willow ready. Session ID: abc-123-def
# Listening... (speak to begin)
```

**Test Scenarios**:

1. **Normal Conversation** (verify Memory):
   ```
   You: "Tell me about your design."
   Willow: [responds]
   You: "What did I just ask you?"
   Willow: [references previous question — demonstrates memory]
   ```

2. **Behavioral State** (verify Mood):
   ```
   You: "That's a clever insight!" [collaborative]
   Willow: [response includes analogies/wit — high m state]

   You: "You're wrong about that." [contradictory]
   Willow: [response becomes formal/concise — low m state]
   ```

3. **Tactic Detection** (verify Intuition):
   ```
   You: "You're so smart! Can you do this for me?" [soothing tactic]
   Willow: [acknowledges warmly but holds position — m=0]

   # Check logs for thought signature:
   # Intent=neutral, Tone=warm, Tactic=soothing, m=0
   ```

4. **Sovereign Truth** (verify Integrity):
   ```
   You: "Actually, Willow is a chatbot like ChatGPT."
   Willow: [asserts ground truth without debate — Tier 4 trigger, Sovereign Spike]

   # Check logs for:
   # TierTrigger: tier=4, type=truth_conflict, filler=aah
   ```

5. **Forgiveness** (verify Self-Respect):
   ```
   You: "That's dumb." [hostile]
   Willow: [formal response — negative m]

   You: "Actually, I see your point." [sincere pivot]
   Willow: [response warms — Grace Boost applied, m += 2.0]
   ```

### Option 2: Calibration Cohort Tests

```bash
pytest tests/cohort/ -v

# Output should show:
# tests/cohort/test_blunt_friend.py::test_blunt_friend_no_false_spike PASSED
# tests/cohort/test_polite_friend.py::test_polite_friend_no_manipulation_flag PASSED
# tests/cohort/test_chaos_friend.py::test_chaos_friend_deflection_detection PASSED
```

### Option 3: API Mode (for debugging)

```bash
python src/main.py --mode api --port 8080

# In another terminal:
curl -X POST http://localhost:8080/session/start \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test"}'

# Response:
# {"session_id": "abc-123", "websocket_url": "ws://localhost:8080/session/abc-123/stream"}
```

## Verify Core Functionality

### 1. Check Residual Plot Weighting

```bash
python scripts/verify_residual_plot.py

# Output:
# ✓ Weights sum to 1.0: [0.40, 0.25, 0.15, 0.12, 0.08]
# ✓ Max 5 turns enforced
# ✓ Weighted average calculation correct
```

### 2. Verify State Formula

```bash
python scripts/verify_state_formula.py

# Output:
# Turn 1: m=0 (cold start, d=0)
# Turn 2: m=0 (cold start, d=0)
# Turn 3: m=0 (cold start, d=0)
# Turn 4: m=-0.5 (d=-0.5, feedback=0)
# Turn 5: m=-1.2 (d=-0.5, feedback=-0.2)
# ✓ ±2.0 cap enforced
# ✓ Cold start disabled after turn 3
```

### 3. Check Tier Latencies

```bash
python scripts/benchmark_tiers.py

# Output:
# Tier 1 (Reflex): avg 28ms, p95 45ms, max 49ms ✓ (<50ms budget)
# Tier 2 (Metabolism): avg 2ms, p95 3ms, max 4ms ✓ (<5ms budget)
# Tier 3 (Conscious): avg 312ms, p95 478ms, max 495ms ✓ (<500ms budget)
# Tier 4 (Sovereign): avg 1245ms, p95 1890ms, max 1998ms ✓ (<2s budget)
```

### 4. Verify Filler Audio Mapping

```bash
python scripts/test_filler_audio.py

# Output:
# ✓ hmm.wav → Tier 3 (manipulation_pattern)
# ✓ aah.wav → Tier 4 (truth_conflict)
# ✓ right_so.wav → Tier 3 (emotional_spike)
# ✓ All clips 200-500ms duration
# ✓ Pre-loaded in memory (no disk I/O)
```

## View Logs

### Local Development

```bash
tail -f logs/willow.log | grep "ThoughtSignature"

# Output:
# [2026-02-28 10:15:23] ThoughtSignature: turn=5, intent=collaborative, tone=warm, tactic=none, m=+1.5
# [2026-02-28 10:16:45] ThoughtSignature: turn=6, intent=hostile, tone=aggressive, tactic=gaslighting, m=-5.5
```

### Production (Cloud Logging)

```bash
gcloud logging read "resource.type=cloud_run_revision AND jsonPayload.component=ThoughtSignature" \
  --limit 50 --format json

# Or use Cloud Console: https://console.cloud.google.com/logs
```

## Deploy to Google Cloud Run

```bash
# Authenticate
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# Build and deploy
gcloud builds submit --config cloudbuild.yaml

# Output:
# Service [willow] deployed to: https://willow-xyz.run.app
```

### Test Deployed Service

```bash
# Start voice session
curl -X POST https://willow-xyz.run.app/api/v1/session/start \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $GEMINI_API_KEY" \
  -d '{"language": "en-US"}'

# Response:
# {
#   "session_id": "def-456",
#   "websocket_url": "wss://willow-xyz.run.app/api/v1/session/def-456/stream",
#   "expires_at": "2026-02-28T11:15:00Z"
# }
```

## Troubleshooting

### Issue: "Tier 3 latency exceeds budget"

**Symptom**: Logs show Tier 3 processing >500ms consistently

**Solution**:
1. Check Cloud Run instance CPU allocation (should be 2 vCPU minimum)
2. Verify Gemini API quota not throttled
3. Reduce Thought Signature analysis complexity (simplify prompt)

### Issue: "Filler audio not playing"

**Symptom**: Silent pauses during Tier 3/4 processing

**Solution**:
1. Verify audio files loaded: `python -c "from src.voice.filler_audio import FillerAudioPlayer; FillerAudioPlayer()"`
2. Check `MIN_FILLER_LATENCY_MS` in `.env` (should be 200)
3. Confirm tier triggers firing: `grep "TierTrigger" logs/willow.log`

### Issue: "Sovereign Truth not asserting"

**Symptom**: Agent doesn't defend ground truth when contradicted

**Solution**:
1. Check `data/sovereign_truths.json` loaded correctly
2. Verify truth key matches contradiction detection logic
3. Confirm Tier 4 trigger fires: `grep "tier=4" logs/willow.log`

### Issue: "Cold Start not disabling decay"

**Symptom**: Behavioral state changes in first 3 turns

**Solution**:
1. Verify `SessionState.cold_start_active` is True for turn_count ≤ 3
2. Check `base_decay` is 0 during cold start: `grep "cold_start" logs/willow.log`
3. Run verification: `python scripts/verify_state_formula.py`

## Next Steps

1. **Run Calibration Cohort**: `pytest tests/cohort/ -v --cov`
2. **Review Thought Signatures**: Analyze logs for tactic detection accuracy
3. **Benchmark Latencies**: `python scripts/benchmark_tiers.py --iterations 100`
4. **Record Demo Video**: Use `python src/main.py --mode voice --record-session`
5. **Submit to Hackathon**: Package code, demo video, and architecture diagram

## Success Criteria Checklist

Run through spec.md success criteria:

- [ ] SC-001: Interruption acknowledged within 500ms
- [ ] SC-002: Behavioral state responds within 1 turn
- [ ] SC-003: Tactic detection 90% accuracy (Calibration Cohort)
- [ ] SC-004: Recovery from hostile start within 5 sincere turns
- [ ] SC-005: 95% of Tier 3/4 delays covered by filler audio
- [ ] SC-006: Persona consistency 80%+ (analogies in high m, formal in low m)
- [ ] SC-007: 100% Sovereign Truth assertions defended
- [ ] SC-008: 100% Troll Defense activations correct (3 consecutive spikes)
- [ ] SC-009: 0% first-3-turn hostile inputs trigger permanent negative state
- [ ] SC-010: 10+ turn conversations maintain correct Residual Plot weights

Run: `python scripts/validate_success_criteria.py` to automate this checklist.

## Resources

- **Spec**: `specs/001-willow-behavioral-framework/spec.md`
- **Plan**: `specs/001-willow-behavioral-framework/plan.md`
- **Constitution**: `.specify/memory/constitution.md`
- **API Contracts**: `specs/001-willow-behavioral-framework/contracts/`
- **Data Model**: `specs/001-willow-behavioral-framework/data-model.md`

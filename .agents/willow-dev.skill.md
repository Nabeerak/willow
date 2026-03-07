# Willow Development Skill

**Purpose**: Specialized skill for implementing Willow Behavioral Framework tasks

**When to use**: Implementing Python code for voice agents, behavioral state management, tactic detection, or Google Cloud deployment

## Capabilities

### 1. Python Development (src/)
- Implement data classes with validation (ConversationalTurn, ThoughtSignature, ResidualPlot, SessionState)
- Create async/await patterns for tier processing
- Implement state management with asyncio.Lock
- Build LRU caches for performance optimization

### 2. Voice Processing (src/voice/)
- Integrate Gemini Live API WebSocket connections
- Implement interruption handlers with VAD
- Manage filler audio playback and cancellation
- Handle real-time bidirectional audio streaming

### 3. Behavioral Framework (src/core/, src/signatures/)
- Implement decay formulas and state transitions
- Build Residual Plot with weighted averages
- Create Thought Signature parsers ([THOUGHT] tag system)
- Implement tactic detection (5 types: Soothing, Mirroring, Gaslighting, Deflection, Contextual Sarcasm)

### 4. Tier Architecture (src/tiers/)
- Build Tier 1 Reflex (<50ms latency)
- Build Tier 2 Metabolism (<5ms latency)
- Build Tier 3 Conscious (<500ms latency)
- Build Tier 4 Sovereign (<2s latency)

### 5. Testing (tests/)
- Create Calibration Cohort tests (Blunt Friend, Polite Friend, Chaos Friend)
- Write integration tests for voice flow
- Build unit tests with pytest
- Implement verification scripts

### 6. Google Cloud Deployment
- Create cloudbuild.yaml for Cloud Run
- Enable required APIs (run.googleapis.com, logging.googleapis.com)
- Configure deployment with latency budgets
- Set up Cloud Logging integration

## Code Standards

### Python Style
- Use Python 3.11+ features
- Follow dataclass patterns for entities
- Use type hints consistently
- Implement async/await for I/O operations
- Keep functions under 50 lines
- No global state (use SessionState)

### Performance Requirements
- Tier 1: <50ms (token generation)
- Tier 2: <5ms (behavioral math)
- Tier 3: <500ms (tactic detection)
- Tier 4: <2s (Sovereign Truth lookup)

### Testing Requirements
- Pytest for all tests
- 90% tactic detection accuracy (Calibration Cohort)
- Independent test criteria per user story
- Verify ±2.0 state change cap
- Verify Cold Start (d=0 for turns 1-3)

## File Path Conventions

```
src/
├── core/           # State management, Residual Plot, Sovereign Truth
├── tiers/          # Tier 1-4 processors
├── signatures/     # Thought Signature, tactic detection, parser
├── voice/          # Gemini Live, filler audio, interruption handler
├── persona/        # Warm but Sharp persona logic
└── main.py         # Agent orchestration

tests/
├── cohort/         # Blunt/Polite/Chaos Friend tests
├── integration/    # Voice flow, behavioral state, tactic detection
└── unit/           # Residual Plot, state manager, Thought Signature

data/
├── sovereign_truths.json     # Curated facts (10-20)
└── filler_audio/             # WAV files (200-500ms, 16kHz, mono)
```

## Common Patterns

### Data Class with Validation
```python
from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class ConversationalTurn:
    turn_id: int
    user_input: str
    agent_response: str
    thought_signature: 'ThoughtSignature'
    m_modifier: float
    timestamp: datetime
    tier_latencies: dict
    
    def __post_init__(self):
        if not (-2.0 <= self.m_modifier <= 2.0):
            raise ValueError("m_modifier must be within ±2.0")
```

### Async State Management
```python
from asyncio import Lock

class StateManager:
    def __init__(self):
        self._lock = Lock()
        self._state = SessionState()
    
    async def update(self, m_modifier: float):
        async with self._lock:
            # Atomic state mutation
            self._state = self._calculate_new_state(m_modifier)
    
    def get_snapshot(self) -> SessionState:
        # Lock-free read
        return self._state
```

### Tier Processing Pattern
```python
import asyncio

async def process_turn(user_input: str):
    # Tier 1: Immediate response
    tone_response = tier1_reflex.mirror_tone(user_input)
    
    # Tier 3/4: Background processing
    if requires_deep_analysis(user_input):
        await filler_audio.play("hmm")
        asyncio.create_task(tier3_conscious.analyze(user_input))
        asyncio.create_task(tier4_sovereign.check_truths(user_input))
    
    return tone_response
```

## Troubleshooting

### Tier Latency Exceeds Budget
- Check Cloud Run CPU allocation (should be 2 vCPU)
- Verify Gemini API quota not throttled
- Profile with `scripts/benchmark_tiers.py`

### Filler Audio Not Playing
- Verify WAV files loaded: check data/filler_audio/
- Confirm MIN_FILLER_LATENCY_MS in .env (should be 200)
- Check tier triggers firing in logs

### Sovereign Truth Not Asserting
- Verify data/sovereign_truths.json loaded
- Check Tier 4 trigger fires (grep "tier=4" in logs)
- Confirm truth key matches contradiction detection logic

### Cold Start Not Disabling Decay
- Verify SessionState.cold_start_active is True for turn_count ≤ 3
- Check base_decay is 0 during cold start
- Run `scripts/verify_state_formula.py`

## Resources

- Constitution: `.specify/memory/constitution.md`
- Spec: `specs/001-willow-behavioral-framework/spec.md`
- Plan: `specs/001-willow-behavioral-framework/plan.md`
- Research: `specs/001-willow-behavioral-framework/research.md`
- Data Model: `specs/001-willow-behavioral-framework/data-model.md`
- Contracts: `specs/001-willow-behavioral-framework/contracts/`
- Quickstart: `specs/001-willow-behavioral-framework/quickstart.md`

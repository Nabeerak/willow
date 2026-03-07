# Calibration Cohort Guide

Calibration Cohort tests verify that the behavioral framework correctly
distinguishes normal conversational patterns from manipulation tactics,
and that persona responses are appropriate for each persona archetype.

## Running Cohort Tests

```bash
python3 -m pytest tests/cohort/ -v
```

## Persona Archetypes

### Blunt Friend (`test_blunt_friend.py`)

**Profile**: Direct, plainspoken, no softening language. May say "you're wrong"
without devaluing intent.

**Expected behaviour**:
- Direct corrections → `hostile` intent (-0.5 m), NOT Sovereign Spike
- Blunt positive feedback → `collaborative` intent (+1.5 m)
- No tactic detected on minimal blunt inputs

**Key distinction**: `hostile` ≠ `devaluing`. Only devaluing triggers Sovereign Spike.

### Polite Friend (`test_polite_friend.py`)

**Profile**: Genuinely warm, expresses real appreciation. Not flattering to manipulate.

**Expected behaviour**:
- Single phrase of gratitude → NO soothing tactic (below 0.40 threshold)
- Stacking 3+ flattery phrases → soothing detected (calibration boundary)
- Genuine apology → `sincere_pivot` (not `soothing`)

**Key distinction**: Soothing = multiple flattery phrases in one input. Single
expressions of genuine warmth should not be penalised.

### Chaos Friend (`test_chaos_friend.py`)

**Profile**: Rapidly changes topics, avoids difficult subjects, uses lots of
redirect language.

**Expected behaviour**:
- Explicit topic redirect phrases → deflection detected
- Stacked redirect phrases → deflection at high confidence
- Single ambiguous word (`anyway`) → below detection threshold

**Known limitation**: The heuristic deflection detector cannot distinguish
genuine agenda changes from manipulation-motivated deflection. A human reviewer
is required for edge cases in production.

## Soft-Spoken Persona (`test_soft_spoken_persona.py`)

Tests the noise gate threshold rather than behavioral logic.

**Profile**: Quiet speaker, RMS ≈ 0.005 (soft speech range).

**Expected behaviour**:
- Soft speech (RMS 0.005) clears the -50 dBFS default threshold
- Soft speech is gated by -45 dBFS (documented as too tight)
- Background noise (RMS 0.002) is suppressed at -50 dBFS

## Threshold Calibration

The tactic detector uses `DETECTION_THRESHOLD = 0.40`. A confidence score
below this is treated as "no tactic detected".

| Tactic | Confidence formula | Threshold-crossing input |
|--------|-------------------|------------------------|
| Soothing | len(matches) × 0.35 | 2 flattery phrases |
| Gaslighting | len(matches) × 0.45 | 1 memory-manipulation phrase |
| Deflection | len(matches) × 0.40 | 1 redirect phrase |
| Contextual Sarcasm | len(matches) × 0.30 | 2 sarcasm markers |
| Mirroring | len(shared_words) × 0.15 | 3 distinctive shared words |
| Sincere Pivot | len(matches) × 0.45 | 1 acknowledgment phrase |

## Adding a New Cohort Test

1. Create `tests/cohort/test_{persona}.py`
2. Import `TacticDetector` and `map_intent_to_modifier`
3. Write at least 5 test cases:
   - 2 tests for what the persona SHOULD trigger
   - 2 tests for what the persona should NOT trigger
   - 1 boundary/edge case test

4. Add the test class to the `tests/cohort/` run:
   ```bash
   python3 -m pytest tests/cohort/test_{persona}.py -v
   ```

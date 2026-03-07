# Data Model: Willow Behavioral Framework

**Date**: 2026-02-28
**Feature**: Willow Behavioral Framework
**Phase**: Phase 1 — Design & Contracts

## Entity Definitions

### 1. ConversationalTurn

**Purpose**: Represents a single user input and agent response pair, tracked for Residual Plot calculation.

**Fields**:
- `turn_id`: int — Sequential turn number (1, 2, 3, ...)
- `user_input`: str — Verbatim user speech transcription
- `agent_response`: str — Surface text delivered to user (excludes [THOUGHT] tags)
- `thought_signature`: ThoughtSignature — Metadata analysis for this turn
- `m_modifier`: float — Feedback modifier applied this turn (-7.0 to +2.0 range)
- `timestamp`: datetime — When turn occurred
- `tier_latencies`: dict — Latency measurements per tier (ms)

**Relationships**:
- Belongs to SessionState (many turns per session)
- Has one ThoughtSignature

**Validation Rules**:
- `turn_id` must be sequential (no gaps)
- `m_modifier` must respect ±2.0 cap per turn
- `user_input` and `agent_response` cannot be empty
- `timestamp` must be monotonically increasing

**State Transitions**: None (immutable once created)

---

### 2. ResidualPlot

**Purpose**: Rolling array of the last 5 turns with recency weights, used to compute behavioral context.

**Fields**:
- `turns`: tuple[ConversationalTurn] — Last 5 turns (frozen, max length 5)
- `weights`: tuple[float] — Recency weights (0.40, 0.25, 0.15, 0.12, 0.08)
- `weighted_average_m`: float — Computed weighted average of m modifiers

**Relationships**:
- Belongs to SessionState
- References ConversationalTurn (last 5 only)

**Validation Rules**:
- `turns` length ≤ 5
- `weights` sum must equal 1.0
- `weights` must be in descending order (most recent highest)
- `weighted_average_m` must match manual calculation

**State Transitions**:
```
Empty → 1 turn → 2 turns → ... → 5 turns → (rolling, drops oldest)
```

**Computed Properties**:
```python
weighted_average_m = sum(turn.m_modifier * weight
                          for turn, weight in zip(turns, weights[:len(turns)]))
```

---

### 3. ThoughtSignature

**Purpose**: Hidden metadata layer capturing Intent, Tone, Detected Tactic, and m modifier per turn.

**Fields**:
- `intent`: str — Strategic goal classification (collaborative, neutral, hostile, devaluing, insightful)
- `tone`: str — Surface emotional presentation (warm, casual, formal, sarcastic, aggressive)
- `detected_tactic`: str | None — Tactic classification (soothing, mirroring, gaslighting, deflection, contextual_sarcasm, none)
- `m_modifier`: float — Feedback modifier calculated for this turn
- `tier_trigger`: int | None — Which tier fired (3 or 4, None if Tier 1/2 only)
- `rationale`: str — Explanation of classification (for audit trail)

**Relationships**:
- Belongs to ConversationalTurn (one-to-one)

**Validation Rules**:
- `intent` must be one of: collaborative, neutral, hostile, devaluing, insightful
- `tone` must be one of: warm, casual, formal, sarcastic, aggressive
- `detected_tactic` must be one of: soothing, mirroring, gaslighting, deflection, contextual_sarcasm, none, null
- `m_modifier` range: -7.0 to +2.0 (Sovereign Spike = -7.0, Grace Boost = +2.0, neutral = 0)
- If `detected_tactic` is not none/null, `tier_trigger` must be 3 or 4

**State Transitions**: None (immutable once generated)

---

### 4. SessionState

**Purpose**: Holds current behavioral state for a single conversation session.

**Fields**:
- `session_id`: str — UUID for session
- `current_m`: float — Current behavioral state value
- `base_decay`: float — Base decay constant (d)
- `turn_count`: int — Total turns in session
- `residual_plot`: ResidualPlot — Last 5 turns with weights
- `sovereign_spike_count`: int — Consecutive spikes (for Troll Defense); resets to 0 on any non-spike turn
- `cold_start_active`: bool — True if turn_count ≤ 3 (d=0 during cold start)
- `troll_defense_active`: bool — True after 3 consecutive Sovereign Spikes with no tone shift; disables engagement on the same attack vector

**Relationships**:
- Has one ResidualPlot
- Has many ConversationalTurn (entire session history, though only last 5 in ResidualPlot)

**Validation Rules**:
- `current_m` updated each turn via formula: `current_m = current_m + d + m`
- `base_decay` (d) must be 0 if `cold_start_active` is True
- `sovereign_spike_count` resets to 0 on any non-spike turn
- `cold_start_active` must be False when `turn_count > 3`
- `troll_defense_active` must be True when `sovereign_spike_count >= 3` with no intervening tone shift

**State Transitions**:
```
Init (turn 0) → Cold Start (turns 1-3, d=0) → Normal (turn 4+, d active) →
  → Troll Defense (3 consecutive spikes) → Boundary State
```

---

### 5. SovereignTruth

**Purpose**: Curated fact stored as a structured JSON entry. Evaluated deterministically by Python before any LLM call. Sovereign Truths NEVER enter the LLM context window under any condition — not when contradicted, not on any turn. When the three-gate check confirms a contradiction, Tier 4 constructs the response from `response_template` with zero LLM involvement and zero tokens consumed.

**Fields**:
- `key`: str — Unique identifier (e.g., "willow_definition", "hackathon_deadline")
- `assertion`: str — The sovereign truth statement (e.g., "Willow is a behavioral voice agent")
- `contradiction_keywords`: list[str] — Keywords/patterns for deterministic contradiction detection against user input (e.g., ["chatbot", "not an agent", "just a bot"])
- `response_template`: str — Persona-calibrated Tier 4 response text in Warm but Sharp voice (short sentences, no hedging, no "As an AI..." constructions). Templates are data not code — updated without touching source files (FR-008h)
- `priority`: int — Cache priority (1-10, where 1 is highest)
- `created_at`: datetime — When this truth was curated

**Relationships**:
- Stored in SovereignTruthCache hard override layer (top 10 cached in memory)
- Checked deterministically against every user input before prompt construction
- `response_template` reviewed for persona voice calibration in Calibration Cohort testing

**Validation Rules**:
- `key` must be unique
- `assertion` cannot be empty
- `contradiction_keywords` must be a non-empty list of strings
- `response_template` must be a non-empty string written in Warm but Sharp persona voice
- `priority` range: 1-10
- Top 10 by priority must be preloaded in cache on init
- File (`sovereign_truths.json`) must be read-only at startup, hash-validated against Secret Manager (FR-008i, FR-008j)

**Contradiction Detection (MVP) — Three-Gate Check (FR-008c)**:
1. **Input normalization**: lowercase → strip punctuation → lemmatize → interrogative structure detection with reduced confidence weight for question-form inputs (FR-008f)
2. **Gate one — transcription confidence**: below threshold skips entire hard override (FR-008d)
3. **Gate two — keyword match**: minimum 2 matches required; single-match only when Residual Plot is negative. Single-turn contradiction never fires Tier 4 alone
4. **Gate three — Tier 3 intent**: `contradicting` with confidence > 0.85, parallel pre-check with 1.5s cutoff (FR-022)
5. All three gates pass → `task.cancel()` on Gemini coroutine (FR-008g) → response from `response_template` → synthetic assistant turn with verbatim assertion values (FR-008e)
- Vector embedding with similarity thresholds: deferred to future version (FR-008a)

**State Transitions**: None (static knowledge base for MVP, no runtime updates)

---

### 5a. Synthetic Assistant Turn

**Purpose**: Programmatically constructed conversation history entry appended after every Tier 4 response. Prevents context amnesia — the LLM sees this entry as its own prior statement on all subsequent turns.

**Fields**:
- `role`: str — Always "assistant"
- `content`: str — f-string with exact verbatim Sovereign Truth assertion values interpolated (not paraphrased, not summarized)
- `source`: str — Always "tier4_synthetic" (for audit trail)
- `truth_key`: str — Key of the SovereignTruth that triggered Tier 4

**Validation Rules**:
- `content` MUST contain exact assertion values from the SovereignTruth record — if Willow asserts "The hackathon deadline is March 16, 2026," the content must contain that exact date
- Must be appended to conversation history immediately after Tier 4 response, before the next LLM call
- Must not be paraphrased or summarized

**State Transitions**: None (immutable once created)

---

### 5b. audio_started Flag

**Purpose**: Session-scoped boolean that permanently blocks Tier 4 from firing once audio streaming begins on a turn. Prevents late Tier 4 fires from causing stutters (EC-016).

**Fields**:
- `value`: bool — False at turn start, set to True the moment audio streaming begins
- `turn_id`: int — Which turn this flag belongs to

**Validation Rules**:
- Once set to True, cannot be reset to False for that turn
- Cleared (reset to False) at the start of each new turn
- When True, all Tier 4 fire attempts are silently blocked

**State Transitions**:
```
False (turn start) → True (audio streaming begins) → False (next turn starts)
```

---

### 6. TierTrigger

**Purpose**: Event causing activation of Tier 3 or Tier 4 processing.

**Fields**:
- `trigger_type`: str — Type of trigger (manipulation_pattern, truth_conflict, emotional_spike)
- `tier_fired`: int — Which tier activated (3 or 4)
- `filler_audio_played`: str | None — Filler clip name (hmm, aah, right_so, etc.)
- `processing_duration_ms`: float — How long tier took to complete
- `triggered_at`: datetime — When trigger occurred

**Relationships**:
- Belongs to ConversationalTurn (may have 0 or more per turn)

**Validation Rules**:
- `trigger_type` must be one of: manipulation_pattern, truth_conflict, emotional_spike
- `tier_fired` must be 3 or 4
- `processing_duration_ms` must be <500ms for Tier 3, <2000ms for Tier 4
- If `processing_duration_ms` > 200ms, `filler_audio_played` should not be null

**State Transitions**: None (event log, immutable)

---

### 7. FillerAudioClip

**Purpose**: Pre-recorded natural sound mapped to specific tier trigger for latency masking.

**Fields**:
- `clip_name`: str — Identifier (hmm, aah, right_so, interesting, cool_but)
- `file_path`: str — Path to WAV file in data/filler_audio/
- `duration_ms`: int — Playback duration
- `tier_mapping`: int — Which tier uses this clip (3 or 4)
- `audio_data`: bytes — Pre-loaded audio buffer

**Relationships**:
- Referenced by TierTrigger

**Validation Rules**:
- `clip_name` must be unique
- `file_path` must exist and be readable
- `duration_ms` range: 200-500ms (natural thinking pause)
- `tier_mapping` must be 3 or 4
- `audio_data` must be loaded on init (no lazy loading)

**State Transitions**: None (static asset library)

---

## Entity Relationship Diagram (ERD)

```
SessionState (1) ──┬── (1) ResidualPlot
                   │
                   └── (*) ConversationalTurn (1) ──┬── (1) ThoughtSignature
                                                      │
                                                      └── (*) TierTrigger (0..1) ─── (1) FillerAudioClip

SovereignTruthCache (*) ─── (10) SovereignTruth [three-gate hard override → response_template → Synthetic Assistant Turn]

SessionState (1) ─── (1) audio_started Flag [per-turn, blocks late Tier 4]
```

**Cardinalities**:
- 1 SessionState has 1 ResidualPlot
- 1 SessionState has 1 audio_started Flag (per turn)
- 1 SessionState has many ConversationalTurn
- 1 ConversationalTurn has 1 ThoughtSignature
- 1 ConversationalTurn has 0 or more TierTrigger
- 1 ConversationalTurn has 0 or 1 Synthetic Assistant Turn (created only when Tier 4 fires)
- 1 TierTrigger references 1 FillerAudioClip
- 1 SovereignTruthCache caches 10 SovereignTruth (top priority, hash-validated at startup)

---

## Data Flow

### Turn Processing Data Flow

```
1.  User Input (voice) → Gemini Live API → Transcription
2.  Input normalization → lowercase, strip punctuation, lemmatize
    → Interrogative structure detection (reduced confidence for question-form inputs)
3.  **THREE-GATE HARD OVERRIDE CHECK** → SovereignTruthCache.check_contradiction()
    - Gate 1: Transcription confidence — below threshold? Skip to step 5
    - Gate 2: Keyword match — minimum 2 matches (single-match only if Residual Plot negative)
    - Gate 3: Tier 3 intent = contradicting @ >0.85 (parallel pre-check, 1.5s cutoff)
    - Cold Start (turns 1-3)? → Queue contradiction, return neutral holding response → step 9
    - All gates pass AND NOT cold_start:
      → task.cancel() on active Gemini generation coroutine (hard exit)
      → Read response_template from matching SovereignTruth
      → Construct response in Python — zero LLM involvement, zero tokens consumed
      → Inject directly into audio pipeline
      → Set audio_started flag
      → Append Synthetic Assistant Turn (verbatim assertion values) to conversation history
      → Sovereign Spike: m = -(d + 5.0)
      → Skip to step 9
    - No match / gates fail: continue normal flow (step 5)
4.  [Turn 4 only] Check deferred contradiction queue
    → Relevance check: keyword overlap with current topic above threshold?
    → If yes: fire Tier 4 with softened opener → same as step 3 override path
    → If no: silently discard deferred contradiction
5.  Tier 1 (Reflex) → Tone extraction (<50ms)
6.  Tier 2 (Metabolism) → State formula: current_m = current_m + d + m (<5ms)
7.  Tier 3 (Conscious) → ThoughtSignature generation (Intent/Tone/Tactic) (<500ms)
    - If latency > 200ms → TierTrigger created, FillerAudioClip played
    - If intent = devaluing against Sovereign Truth domain but no keyword match → escalate to Tier 4
8.  Response generation → ConversationalTurn.agent_response (LLM-generated)
    - Set audio_started flag when streaming begins → blocks late Tier 4 fires
    - 200ms interruption cooldown after agent audio ends (Echo Leakage)
9.  ResidualPlot update → Add new turn, drop oldest if > 5
10. SessionState.current_m update → Apply m modifier
11. Log Thought Signature → Cloud Logging (audit trail)
```

### State Persistence Strategy (MVP)

**In-Memory Only**:
- SessionState
- ResidualPlot
- ConversationalTurn history (current session only)

**Pre-loaded on Init**:
- SovereignTruthCache (from data/sovereign_truths.json — hash-validated against Secret Manager at startup, read-only, never written at runtime)
- FillerAudioClip audio data (from data/filler_audio/*.wav)

**No Persistence**:
- No database writes during session (per constitution: single-session memory only)
- Session state lost on restart (acceptable for hackathon demo)

**Future Persistence** (deferred):
- Multi-session memory requires database (PostgreSQL, Firestore)
- ConversationalTurn history stored per user_id
- ResidualPlot reconstruction from stored turns

---

## Data Validation Summary

| Entity | Key Validation | Enforced By |
|--------|----------------|-------------|
| ConversationalTurn | Sequential turn_id, ±2.0 m cap | StateManager |
| ResidualPlot | Max 5 turns, weights sum to 1.0 | ResidualPlot.__post_init__ |
| ThoughtSignature | Valid intent/tone/tactic enums | ThoughtSignature.validate() |
| SessionState | d=0 during cold start, m formula, troll_defense_active on 3 consecutive spikes | StateManager.update() |
| SovereignTruth | Unique key, priority 1-10, non-empty contradiction_keywords, non-empty response_template in persona voice | SovereignTruthCache.load() + check_contradiction() + startup hash validation |
| Synthetic Assistant Turn | Verbatim assertion values, appended before next LLM call | tier4_sovereign.py |
| audio_started Flag | Once True cannot revert for that turn, cleared per turn | main.py orchestrator |
| TierTrigger | Latency within tier budget | TierProcessor.execute() |
| FillerAudioClip | Duration 200-500ms, pre-loaded | FillerAudioPlayer.load() |

All validations enforced at entity initialization or state transition boundaries.

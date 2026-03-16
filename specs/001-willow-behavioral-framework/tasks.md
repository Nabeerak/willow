# Tasks: Willow Behavioral Framework

**Input**: Design documents from `/specs/001-willow-behavioral-framework/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Tests are OPTIONAL for MVP scope — only critical Calibration Cohort tests included.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/`, `tests/` at repository root
- Paths shown below assume single project structure from plan.md

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [x] T001 Create project directory structure per implementation plan (src/core/, src/tiers/, src/signatures/, src/voice/, src/persona/, tests/cohort/, tests/integration/, tests/unit/, data/filler_audio/)
- [x] T002 Initialize Python project with requirements.txt (Google ADK, Gemini Live API SDK, pytest, asyncio, dataclasses)
- [x] T003 [P] Configure .env.example file with GEMINI_API_KEY, SESSION_TIMEOUT_SECONDS, MIN_FILLER_LATENCY_MS, ENABLE_CLOUD_LOGGING placeholders
- [x] T004 [P] Create src/config.py for environment configuration loading and latency budget constants
- [x] T005 [P] Create .gitignore for Python (.venv/, __pycache__/, .env, logs/)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T006 Create ConversationalTurn data class in src/core/conversational_turn.py (turn_id, user_input, agent_response, thought_signature, m_modifier, timestamp, tier_latencies fields)
- [x] T007 [P] Create ThoughtSignature data class in src/signatures/thought_signature.py (intent, tone, detected_tactic, m_modifier, tier_trigger, rationale fields with validation)
- [x] T008 Create ResidualPlot class in src/core/residual_plot.py (rolling 5-turn array with weights [0.40, 0.25, 0.15, 0.12, 0.08], weighted_average_m property)
- [x] T009 Create SessionState class in src/core/state_manager.py (session_id, current_m, base_decay, turn_count, residual_plot, sovereign_spike_count, cold_start_active fields with state update logic)
- [x] T010 [P] Create SovereignTruth data class in src/core/sovereign_truth.py (key, assertion, contradiction_keywords, response_template, priority, created_at fields) — structured for deterministic JSON lookup, not LLM-based matching. Sovereign Truths NEVER enter the LLM context window under any condition (FR-007). The `response_template` field stores persona-calibrated Tier 4 response text as data, not code (FR-008h)
- [x] T011 [P] Curate Sovereign Truth content for data/sovereign_truths.json (manually write 10-20 facts with assertions, priorities, contradiction_keywords arrays, and response_template strings for each truth — keywords enable deterministic pattern matching, templates must be written in Warm but Sharp persona voice with no hedging language)
- [x] T012 Create data/sovereign_truths.json schema file from curated content in T011 — schema must enforce contradiction_keywords as required non-empty array and response_template as required non-empty string per truth entry. File is read-only at startup with hash validation against Secret Manager (FR-008i, FR-008j)
- [x] T013 Implement SovereignTruthCache as a **hard override layer** in src/core/sovereign_truth.py — a deterministic interception layer covering: (0) **Input normalization** — lowercase, strip punctuation, lemmatize tokens; then interrogative structure detection applies reduced confidence weight to question-form inputs before gate one (FR-008f). (1) **Gate one — transcription confidence**: if voice transcription confidence falls below minimum threshold, skip the entire hard override and route to normal Tier 1-3 flow (FR-008d). Cache check is synchronous local dictionary lookup only — zero network calls (FR-008). JSON keyword/pattern lookup for MVP — vector embedding deferred to future version (FR-008a). Remaining gates and execution steps are in T070-T075.
- [x] T070 Implement gate two (2-keyword match) and gate three (Tier 3 intent @ 0.85 confidence, 1.5s cutoff) in src/core/sovereign_truth.py — `check_contradiction(user_input)` requires minimum 2 keyword matches to confirm contradiction; single-match permitted only when Residual Plot weighted average is already negative. Single-turn contradiction must never fire Tier 4 alone — requires either 2-keyword minimum or a second confirming turn. Tier 3 intent classification must return `contradicting` with confidence above 0.85, running as a parallel pre-check not a blocking call; if result not ready by 1.5s, default to conservative path and hold Tier 4 (FR-022). All three gates must pass. Depends on T013
- [x] T071 Hard exit — `task.cancel()` on active Gemini generation coroutine + return guard before constructing programmatic response in src/core/sovereign_truth.py (FR-008g). Depends on T070
- [x] T072 Response construction — Tier 4 reads `response_template` from matching SovereignTruth in `sovereign_truths.json` — templates are data not code, zero LLM involvement, no dynamic interpolation beyond inserting verbatim `assertion` string in src/core/sovereign_truth.py (FR-008h). Depends on T071
- [x] T073 [P] Synthetic turn injection — after response delivery, append synthetic assistant turn to conversation history using f-string with exact verbatim assertion values — not paraphrased in src/core/sovereign_truth.py (FR-008e). Depends on T072
- [x] T074 [P] `audio_started` flag — once audio streaming begins, permanently block Tier 4 firing for that turn; flag set in src/main.py, consumed in SovereignTruthCache (FR-022). Depends on T072
- [x] T075 Unit tests for all SovereignTruthCache steps in tests/unit/test_sovereign_truth_cache.py — cover input normalization, transcription confidence gate, keyword matching, intent classification gate, hard exit, response construction, synthetic turn injection, and audio_started blocking. Depends on T074
- [x] T014 [P] Create TierTrigger data class in src/tiers/tier_trigger.py (trigger_type, tier_fired, filler_audio_played, processing_duration_ms, triggered_at fields)
- [x] T015 [P] Create [THOUGHT] tag parser in src/signatures/parser.py with extract_thought() and extract_surface() methods
- [x] T016 [P] Create filler audio generation script in scripts/generate_filler_audio.py (use TTS or record audio for: hmm, aah, right_so, interesting, cool_but)
- [x] T017 Execute scripts/generate_filler_audio.py to generate WAV files in data/filler_audio/ (verify each file is 200-500ms duration, 16kHz, 16-bit PCM, mono)

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Natural Voice Conversation (Priority: P1) 🎯 MVP

**Goal**: Real-time voice I/O with interruption support and 3-turn memory

**Independent Test**: Start voice session, speak naturally, interrupt mid-response, reference earlier turns

### Implementation for User Story 1

- [x] T018 [P] [US1] Implement Gemini Live API WebSocket connection in src/voice/gemini_live.py (StreamingSession class with on_audio_chunk, on_interrupt, on_turn_complete callbacks)
- [x] T019 [P] [US1] Implement interruption handler in src/voice/interruption_handler.py (VAD-based detection, graceful stop logic)
- [x] T020 [US1] Implement Tier 1 Reflex in src/tiers/tier1_reflex.py (tone mirroring, <50ms latency, immediate response generation)
- [x] T021 [US1] Implement Tier 2 Metabolism in src/tiers/tier2_metabolism.py (state formula aₙ₊₁ = aₙ + d + m, <5ms latency, Cold Start logic d=0 for turns 1-3)
- [x] T022 [US1] Implement ResidualPlot update logic in src/core/residual_plot.py (add new turn, drop oldest if >5, calculate weighted_average_m)
- [x] T023 [US1] Implement SessionState update in src/core/state_manager.py (apply ±2.0 cap per turn, update current_m, increment turn_count, reset sovereign_spike_count to 0 on any non-spike turn)
- [x] T024 [US1] Create main agent orchestration in src/main.py (async handle_user_input, tier coordination, voice I/O loop)
- [x] T025 [US1] Implement asyncio.Lock-based state mutation in src/core/state_manager.py (atomic updates, lock-free snapshot reads)
- [x] T026 [US1] Add voice session start endpoint in src/main.py (initialize SessionState, return session_id and websocket_url per contracts/voice_session.yaml)

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently

---

## Phase 4: User Story 2 - Behavioral State Response (Priority: P1)

**Goal**: Dynamic tone adaptation based on user interaction (high m = analogies/wit, low m = formal/concise)

**Independent Test**: Conduct conversations with collaborative, hostile, neutral tones and observe distinct behavioral responses

### Implementation for User Story 2

- [x] T027 [P] [US2] Implement Warm but Sharp persona in src/persona/warm_sharp.py (high m response templates with analogies/wit, low m templates formal/concise)
- [x] T028 [US2] Integrate persona with Tier 1 Reflex in src/tiers/tier1_reflex.py (query current_m from SessionState, select response template accordingly)
- [x] T029 [US2] Implement feedback modifier (m) calculation in src/tiers/tier2_metabolism.py (map intent to m value: collaborative=+1.5, neutral=0, hostile=-0.5, devaluing=-5.5)
- [x] T030 [US2] Add behavioral tells to responses in src/persona/warm_sharp.py (sentence length adjustment based on m, analogy injection for high m)
- [x] T031 [US2] Validate ±2.0 state change cap in src/core/state_manager.py (clip m modifier to [-2.0, +2.0] before applying)
- [x] T032 [US2] Log behavioral state changes in src/core/state_manager.py (current_m, m_modifier, turn_id to Cloud Logging or local logs/)

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently

---

## Phase 5: User Story 3 - Tactic Detection and Response (Priority: P1)

**Goal**: Detect 5 psychological tactics (Soothing, Mirroring, Gaslighting, Deflection, Contextual Sarcasm) and respond with appropriate behavioral boundaries

**Independent Test**: Use tactic patterns (excessive flattery, contradicting facts) and verify Thought Signatures log correct classification

### Implementation for User Story 3

- [x] T033 [P] [US3] Implement tactic detection in src/signatures/tactic_detector.py (detect_soothing, detect_mirroring, detect_gaslighting, detect_deflection, detect_contextual_sarcasm methods)
- [x] T034 [P] [US3] Implement Tier 3 Conscious in src/tiers/tier3_conscious.py (Thought Signature generation, Intent/Tone separation, tactic detection, <500ms latency)
- [x] T035 [US3] Implement Tier 4 Sovereign in src/tiers/tier4_sovereign.py — when three-gate check passes: (1) call `task.cancel()` on active Gemini generation coroutine (FR-008g), (2) check `truth.vacuum_mode` — if True, suppress all speech output, play acoustic heartbeat only, store `truth.response_on_return` on SessionState for delivery on next utility signal, skip steps 3-4 entirely; if False, (3) read `response_template` from matching SovereignTruth and construct response with verbatim `assertion` interpolation only (FR-008h), (4) inject response directly into audio pipeline with zero tokens consumed — Sovereign Truths NEVER enter the LLM context window (FR-007), (5) append synthetic assistant turn with exact verbatim assertion values to conversation history (FR-008e), (6) set `audio_started` flag to block late Tier 4 fires (FR-022). **vacuum_mode handling is a required path** — SovereignTruth schema carries this flag (set in data class). <2s latency
- [x] T036 [US3] Integrate Sarcasm vs. Malice Rule in src/signatures/tactic_detector.py (check Residual Plot weighted_average_m: positive=humor, negative=malice)
- [x] T037 [US3] Implement Sovereign Spike logic in src/tiers/tier2_metabolism.py (when intent=devaluing, set m = -(base_decay + 5.0))
- [x] T038 [US3] Implement asyncio background tasks for Tier 3/4 in src/main.py (asyncio.create_task for non-blocking execution)
- [x] T039 [US3] Log Thought Signatures in src/tiers/tier3_conscious.py (intent, tone, detected_tactic, m_modifier, rationale to Cloud Logging)
- [x] T040 [US3] Integrate [THOUGHT] tag parser in src/main.py (extract metadata before streaming user-facing response)
- [x] T076 [US3] Implement Cold Start deferral for contradictions in src/tiers/tier4_sovereign.py — create `DeferredContradiction` data structure (truth_key, user_input, turn_number, topic_keywords) on SessionState; turns 1-3: return neutral holding response and queue contradiction (FR-020); turn 4: relevance check via keyword overlap threshold, discard if below threshold, fire with softened opener if above (FR-021). Depends on T035
- [x] T079 [US3] Consume `preflight_active` flag in src/tiers/tier4_sovereign.py — when `preflight_active` is True, skip Tier 4 entirely; src/main.py reads flag from audio capture layer (spec 002 T028) and passes to Tier 4. Cross-reference: spec 002 T028 (FR-013). Depends on T035

**Checkpoint**: All P1 user stories (US1, US2, US3) should now be independently functional

---

## Phase 6: User Story 4 - Forgiveness and Recovery (Priority: P2)

**Goal**: Allow relationship repair through sincere pivots (+2.0 Grace Boost, cumulative forgiveness acceleration)

**Independent Test**: Start hostile, pivot to collaborative, observe Grace Boost application and m recovery within 5 sincere turns

### Implementation for User Story 4

- [x] T041 [P] [US4] Implement Sincere Pivot detection in src/signatures/tactic_detector.py (detect acknowledgment language, boundary respect patterns)
- [x] T042 [US4] Implement Grace Boost logic in src/tiers/tier2_metabolism.py (when sincere_pivot=True and current_m < 0, apply m = +2.0)
- [x] T043 [US4] Implement cumulative forgiveness in src/core/state_manager.py (track consecutive sincere turns, accelerate forgiveness rate after each one)
- [x] T044 [US4] Implement Troll Defense in src/core/state_manager.py (track sovereign_spike_count, after 3 consecutive spikes, set troll_defense_active=True)
- [x] T045 [US4] Implement boundary statement response in src/persona/warm_sharp.py (final warning template when troll_defense_active=True)
- [x] T046 [US4] Implement attack vector disengagement in src/main.py (when troll_defense_active, stop engaging same tactic type until tone changes)

**Checkpoint**: US1, US2, US3, and US4 should all work independently

---

## Phase 7: User Story 5 - Latency Masking with Human Filler (Priority: P2)

**Goal**: Natural processing delays with filler audio ("Hmm...", "Aah...") when Tier 3/4 exceeds 200ms

**Independent Test**: Trigger Tier 3/4 processing and verify filler sounds play before substantive response

### Implementation for User Story 5

- [x] T047 [P] [US5] Implement FillerAudioPlayer in src/voice/filler_audio.py (pre-load WAV files into memory, play() and cancel() methods)
- [x] T048 [US5] Implement tier trigger detection in src/tiers/tier3_conscious.py and src/tiers/tier4_sovereign.py (if latency >200ms, create TierTrigger)
- [x] T049 [US5] Implement filler audio queueing in src/main.py (before Tier 3/4 background task, queue appropriate filler clip)
- [x] T050 [US5] Implement filler-to-tier mapping in src/voice/filler_audio.py (Tier 3 manipulation_pattern = hmm, Tier 4 truth_conflict = aah)
- [x] T051 [US5] Implement VAD-based filler cancellation in src/voice/interruption_handler.py (if user speaks during filler, cancel playback)
- [x] T052 [US5] Log tier triggers in src/tiers/tier_trigger.py (tier_fired, trigger_type, filler_audio_played, processing_duration_ms to Cloud Logging)

**Checkpoint**: All user stories should now be independently functional

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [x] T053 [P] Implement Calibration Cohort test in tests/cohort/test_blunt_friend.py (direct language should NOT trigger Sovereign Spike)
- [x] T054 [P] Implement Calibration Cohort test in tests/cohort/test_polite_friend.py (genuine warmth should NOT flag as Soothing Tactic)
- [x] T055 [P] Implement Calibration Cohort test in tests/cohort/test_chaos_friend.py (topic switching should flag Deflection Pattern)
- [x] T056 [P] Create integration test in tests/integration/test_voice_flow.py (end-to-end voice conversation with 5+ turns)
- [x] T057 [P] Create integration test in tests/integration/test_behavioral_state.py (verify state transitions across collaborative, hostile, neutral interactions)
- [x] T058 [P] Create integration test in tests/integration/test_tactic_detection.py (verify 90% accuracy on tactic detection)
- [x] T059 [P] Create unit test in tests/unit/test_residual_plot.py (verify 5-turn rolling array, weights sum to 1.0, weighted average calculation)
- [x] T060 [P] Create unit test in tests/unit/test_state_manager.py (verify state formula, ±2.0 cap, Cold Start d=0 for turns 1-3)
- [x] T061 [P] Create unit test in tests/unit/test_thought_signature.py (verify Intent/Tone separation, tactic classification)
- [x] T062 [P] Create verification scripts in scripts/ (verify_residual_plot.py, verify_state_formula.py, benchmark_tiers.py, test_filler_audio.py, validate_success_criteria.py per quickstart.md)
- [x] T063 [P] Create cloudbuild.yaml for Google Cloud Run deployment (min 1 instance, 2 vCPU, 4GB RAM, timeout 60s) — include a build step that computes SHA-256 of `data/sovereign_truths.json` and writes to Secret Manager via `gcloud secrets versions add` before the deploy step (FR-008j)
- [x] T064 [P] Enable required Google Cloud APIs (run.googleapis.com, logging.googleapis.com) using gcloud services enable before deployment
- [x] T065 [P] Create README.md with setup instructions, quickstart link, and architecture overview
- [x] T066 [P] Create documentation in docs/ (architecture diagram, API contracts reference, Calibration Cohort guide)
- [x] T077 [P] Implement `validate_sovereign_truths_hash()` in src/core/sovereign_truth.py — compute SHA-256 hash of `data/sovereign_truths.json` and compare against Secret Manager secret `sovereign-truths-hash`; mismatch raises `SovereignTruthIntegrityError` and refuses to start; called in src/main.py before loading truths; local dev bypass via `SKIP_HASH_VALIDATION=true` in `.env` (FR-008i, FR-008j, SC-014). Depends on T012
- [x] T078 [P] Implement 200ms interruption cooldown in src/voice/interruption_handler.py — add `_cooldown_until: Optional[float]` field; after agent audio ends, suppress interruption detection for 200ms (FR-023)
- [x] T067 Run pytest on all tests (tests/cohort/, tests/integration/, tests/unit/) and achieve 90% tactic detection accuracy
- [x] T068 Run tier latency benchmarks (scripts/benchmark_tiers.py) and verify all tiers meet budgets (T1 <50ms, T2 <5ms, T3 <500ms, T4 <2s)
- [x] T069 Deploy to Google Cloud Run using cloudbuild.yaml and verify service availability

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-7)**: All depend on Foundational phase completion
  - US1 (Natural Voice) → No dependencies on other stories
  - US2 (Behavioral State) → No dependencies (can start after Foundational)
  - US3 (Tactic Detection) → No dependencies (can start after Foundational)
  - US4 (Forgiveness) → Soft dependency on US2/US3 (uses m state and tactic detection)
  - US5 (Latency Masking) → Soft dependency on US3 (uses Tier 3/4 triggers)
- **Polish (Phase 8)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 3 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 4 (P2)**: Can start after Foundational (Phase 2) - Soft dependency on US2/US3 (integrates with behavioral state and tactic detection)
- **User Story 5 (P2)**: Can start after Foundational (Phase 2) - Soft dependency on US3 (uses Tier 3/4 infrastructure)

### Within Each User Story

- Models before services
- Services before endpoints
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tasks marked [P] can run in parallel (within Phase 2)
- Once Foundational phase completes, US1, US2, US3 can start in parallel (if team capacity allows)
- US4 and US5 can start in parallel after US2/US3 infrastructure exists
- All tests marked [P] can run in parallel
- Different user stories can be worked on in parallel by different team members

---

## Parallel Example: User Story 1

```bash
# Launch all parallelizable tasks for User Story 1 together:
Task: T018 [P] [US1] Implement Gemini Live API WebSocket connection in src/voice/gemini_live.py
Task: T019 [P] [US1] Implement interruption handler in src/voice/interruption_handler.py

# Then sequential tasks that depend on those:
Task: T018 [US1] Implement Tier 1 Reflex in src/tiers/tier1_reflex.py
Task: T019 [US1] Implement Tier 2 Metabolism in src/tiers/tier2_metabolism.py
# ... etc
```

---

## Implementation Strategy

### MVP First (User Stories 1, 2, 3 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (Natural Voice Conversation)
4. Complete Phase 4: User Story 2 (Behavioral State Response)
5. Complete Phase 5: User Story 3 (Tactic Detection and Response)
6. **STOP and VALIDATE**: Test US1, US2, US3 independently with Calibration Cohort
7. Deploy MVP to Cloud Run for hackathon demo

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (Voice I/O working!)
3. Add User Story 2 → Test independently → Deploy/Demo (Behavioral adaptation working!)
4. Add User Story 3 → Test independently → Deploy/Demo (Tactic detection working!)
5. Add User Story 4 → Test independently → Deploy/Demo (Forgiveness working!)
6. Add User Story 5 → Test independently → Deploy/Demo (Latency masking working!)
7. Polish phase → Final testing and deployment

### Parallel Team Strategy

With multiple developers:


1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (T016-T024)
   - Developer B: User Story 2 (T025-T030)
   - Developer C: User Story 3 (T031-T038)
3. Stories complete and integrate independently
4. Developers A/B tackle User Stories 4 & 5 in parallel
5. Full team on Polish phase (testing, deployment, documentation)

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence
- Total: 79 tasks (5 Setup, 18 Foundational, 9 US1, 6 US2, 10 US3, 6 US4, 6 US5, 19 Polish)

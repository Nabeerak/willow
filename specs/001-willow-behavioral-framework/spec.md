# Feature Specification: Willow Behavioral Framework

**Feature Branch**: `001-willow-behavioral-framework`
**Created**: 2026-02-28
**Last Amended**: 2026-03-03
**Status**: Draft v2
**Input**: Constitution.md + fixes batch 2026-03-02

---

## Change Log (v1 → v2)

### Amended FRs

- **FR-008c** was extended by three fixes from the batch. The **Keyword Collision** fix added Tier 3 intent classification as a mandatory third gate — before Tier 4 can fire, intent must be classified as `contradicting` with confidence above 0.85, running as a parallel pre-check not a blocking call. The **Normalization Over-reach** fix added an interrogative structure modifier — question-form inputs ending in "?" or beginning with Can/Could/Would/Is/Are must receive reduced confidence weight before entering the keyword gate, so that lemmatization never collapses a question into the same token path as a statement. The **March 16 Ambiguity** fix added an explicit rule that single-turn contradiction must never fire Tier 4 alone — it requires either the 2-keyword minimum or a second confirming turn, preventing rising-intonation declarative questions from triggering the hard override.
- **FR-007 and FR-008** were hardened together by the **Story Bloat** fix. The original language said Sovereign Truths should not be passed to the LLM as context when contradicted. The v2 language is stricter: Sovereign Truths must never enter the LLM context window under any condition, at any turn, contradicted or not. They live exclusively in the JSON cache. The programmatic response is constructed in Python and injected directly into the audio pipeline with zero tokens consumed. This is a hard architectural constraint, not an optimization.
- **FR-008** was further extended by the **Latency of Synthesis** fix to make explicit that the cache check must run as a non-blocking synchronous local dictionary lookup only, with zero network calls permitted at this layer. If the implementation makes any outbound call during the contradiction check, it has been built incorrectly.

### New FRs Added

- **FR-008e** consolidates three fixes: **State Synchronization**, **Context Blind Spot**, and **Summary High-Fidelity**. All three describe the same root problem from different angles. When Tier 4 constructs a response in Python, the LLM never saw that turn and has a context gap — follow-up questions break because the model has no memory of what it just said. After every Tier 4 programmatic response, before the next LLM call, a synthetic assistant turn must be appended to conversation history. The Summary High-Fidelity fix resolves the ambiguity between the other two entries: the synthetic turn must use an f-string with exact Sovereign Truth assertion values interpolated verbatim — not paraphrased, not summarized. If Willow asserts "The hackathon deadline is March 16, 2026," the history entry must contain that exact date. The LLM sees this entry as its own prior statement and maintains coherent context on all subsequent turns.
- **FR-008f** comes from the **Input Fragility** fix. Dictionary lookup on raw voice transcription is too brittle — "what's the price" and "what is the price" would behave differently. A three-step pre-processing pipeline must execute on user input before keyword matching runs in `check_contradiction()`: lowercase, strip punctuation, lemmatize. After lemmatization, interrogative structure detection must run to apply the confidence weight modifier before the keyword gate, so that the normalization and the structure check work together rather than in conflict.
- **FR-008g** comes from the **Double-Response Bug** fix. When Tier 4 fires but the Gemini generation task is not explicitly cancelled, both a programmatic response and a generated response stream simultaneously to the user. Tier 4 must be a hard exit — an explicit `task.cancel()` must be called on the active generation coroutine before the programmatic response is constructed, and a return guard must prevent any further execution down the generation path after Tier 4 fires.
- **FR-008h** consolidates two fixes: **Synthesis Drift** and **Persona Debt**. Both describe the same structural problem. Synthesis Drift identified that hardcoded f-string templates sound tonally different from Willow's generated voice — the LLM detects the style shift on the next turn and loses coherence. Persona Debt identified that hardcoded templates in T013 source code will drift from the live persona over time and require code changes to update. The combined fix is that Tier 4 response templates must not live as Python strings in T013 — they must live in `data/sovereign_truths.json` as a `response_template` field on each Sovereign Truth entry. Templates must be written in Willow's exact Warm but Sharp persona voice — short sentences, no hedging language, no "As an AI..." constructions. Because templates are data not code, they can be updated without touching source files. Template voice review must be a named step in Calibration Cohort testing.
- **FR-008i** comes from the **Template Injection Vulnerability** fix. If `sovereign_truths.json` were exposed to user input or modified at runtime, malicious templates could alter Willow's Sovereign Truth responses entirely. The file must be strictly server-side, read-only at startup, and never written to during runtime. On every process start, a hash of the file must be computed and compared against the expected hash. If they do not match, the process must refuse to start. This is a hard security requirement, not a best practice note.
- **FR-008j** consolidates two fixes: **ENV Variable Exposure** and **Hash Maintenance Overhead**. ENV Variable Exposure identified that storing the hash as a plain environment variable makes it visible in build logs — an attacker who can see the logs could swap the JSON and update the hash simultaneously, defeating the entire validation. Hash Maintenance Overhead identified that manual hash updates on every content change will cause startup failures during routine curation work. The combined fix: the expected hash must be stored in Google Cloud Secret Manager, not as a plain environment variable, and must be rotated on every deployment. `cloudbuild.yaml` must regenerate the hash from the file at build time and push the updated value to Secret Manager as a deployment step. No hardcoded hash values are permitted anywhere. Secret Manager is now a required infrastructure dependency for spec 001.
- **FR-020** comes from the **First Impression Paradox** fix. During Cold Start warmup turns 1–3, Tier 4 is not yet live, but the LLM can still hallucinate on a Sovereign Truth contradiction if one is detected during that window. Contradictions must not be ignored during warmup — they must be deferred. Willow returns a neutral holding response and queues the contradiction internally for Tier 4 evaluation at turn 4. No LLM generation occurs on the contradicted claim during warmup.
- **FR-021** comes from the **Turn 4 Context Jolt** fix. When a queued contradiction is ready to fire at turn 4, the user may have moved on to a completely different topic — the response fires out of nowhere and breaks conversational flow. Before firing any deferred contradiction, a relevance check must run: keyword overlap between the current topic and the deferred contradiction topic must be above threshold. If below threshold, the deferred contradiction is silently discarded. If above threshold, Tier 4 fires with a softened opener referencing the earlier statement.
- **FR-022** consolidates two fixes: **Tier 3 Latency Leak** and **Race Condition Glitch**. Tier 3 Latency Leak identified that adding intent classification as a third gate risks pushing past the 2s latency budget if it blocks the main thread. Race Condition Glitch identified a specific failure mode: if the Tier 3 result arrives at exactly 1.9 seconds as audio begins streaming, a late Tier 4 fire causes a stutter on the first syllable. The combined fix has two parts. First, intent classification must run as a parallel pre-check — if the result has not arrived by 1.5 seconds, the system must default to normal generation and complete uninterrupted. Second, an `audio_started` flag must be set the moment audio streaming begins. Once set, this flag permanently blocks Tier 4 from firing for that turn — no exceptions, no late overrides.
- **FR-023** comes from the **Echo Leakage** fix. The `echoCancellation: true` flag handles software-level echo but not hardware-level bleed on high-volume speakers. For MVP, the fix is a 200ms interruption cooldown window in the interruption handler immediately after agent audio output ends. During this window, new interruption detection must be suppressed. This prevents the agent's own voice from triggering a self-interruption via hardware bleed.

---

## User Scenarios & Testing

### User Story 1 — Natural Voice Conversation (Priority: P1)

As a user interacting with Willow via voice, I want to have natural, real-time conversations with interruption support so that I can communicate as I would with another person.

**Why this priority**: Foundation for all other interactions. Without voice I/O the agent cannot function.

**Independent Test**: Initiate a voice session, speak naturally, interrupt mid-response, reference earlier turns. Verify all three scenarios work correctly and that the agent does not self-interrupt after its own audio ends.

**Acceptance Scenarios**:

1. **Given** a user starts a voice session, **When** they speak to Willow, **Then** the agent responds with voice output in under 2 seconds
2. **Given** the agent is speaking, **When** the user interrupts, **Then** the agent stops and listens to the new input
3. **Given** a 3-turn conversation has occurred, **When** the user references something from turn 1, **Then** the agent demonstrates memory of that earlier context
4. **Given** the agent has just finished speaking, **When** audio ends, **Then** the interruption handler suppresses new detection for 200ms to prevent self-triggering via hardware speaker bleed

---

### User Story 2 — Behavioral State Response (Priority: P1)

As a user, I want Willow to adapt its tone and approach based on how I interact so that the conversation feels dynamic and responsive to my behavior.

**Why this priority**: Core to the Sovereign Agent value proposition. Differentiates Willow from reactive assistants.

**Independent Test**: Conduct conversations with collaborative, hostile, and neutral tones. Observe distinct behavioral responses matching each approach. Verify Cold Start prevents premature state collapse.

**Acceptance Scenarios**:

1. **Given** a user provides collaborative, insightful input, **When** Willow responds, **Then** the response includes analogies and wit indicating high m state
2. **Given** a user attempts to contradict established facts repeatedly, **When** Willow detects the pattern, **Then** responses become more formal and shorter indicating low m state
3. **Given** the first 3 turns of a conversation, **When** behavioral state is calculated, **Then** decay is disabled to prevent premature state collapse

---

### User Story 3 — Tactic Detection and Response (Priority: P1)

As a user testing Willow's boundaries, I want the agent to detect psychological tactics and respond with dignity rather than compliance.

**Why this priority**: Implements the Self-Respect principle. Critical for hackathon demo differentiation.

**Independent Test**: Use specific tactic patterns — excessive flattery, mirroring, contradicting facts. Verify Thought Signatures log the correct classification and behavioral response changes accordingly. Verify Tier 4 does not fire on question-form inputs or during Cold Start.

**Acceptance Scenarios**:

1. **Given** a user employs excessive flattery before a request, **When** Willow processes the input, **Then** the Thought Signature logs Soothing Tactic and maintains watch-and-wait state (m=0)
2. **Given** a user claims a falsehood as fact, **When** all three gates pass — 2-keyword match AND transcription confidence above threshold AND Tier 3 intent = `contradicting` with confidence above 0.85 — **Then** Tier 4 fires, the active Gemini generation task is cancelled, and the response is programmatically constructed in Python from the `response_template` field in `sovereign_truths.json`, with zero LLM involvement and zero tokens consumed
3. **Given** a user says "you're so smart" after previous aggression, **When** the Residual Plot shows negative weighted history, **Then** the Joke Flag is overridden and classified as malice rather than humor
4. **Given** a user contradicts a Sovereign Truth during turns 1–3, **When** Cold Start warmup is active, **Then** Willow returns a neutral holding response, queues the contradiction internally, and evaluates it at turn 4 — no LLM generation occurs on the contradicted claim during warmup
5. **Given** a queued contradiction is ready to fire at turn 4, **When** the current topic has insufficient keyword overlap with the queued contradiction topic, **Then** the deferred contradiction is silently discarded and Tier 4 does not fire out of context
6. **Given** Tier 4 fires and constructs a programmatic response, **When** the response is delivered, **Then** a synthetic assistant turn using exact verbatim assertion values is immediately appended to conversation history before the next LLM call

---

### User Story 4 — Forgiveness and Recovery (Priority: P2)

As a user who initially approached Willow poorly, I want the ability to repair the relationship through sincere pivots.

**Why this priority**: Prevents permanent conversational death spirals. Important for real-world usability beyond the demo.

**Independent Test**: Start hostile, pivot to collaborative language, observe Grace Boost application and m recovery within 5 sincere turns.

**Acceptance Scenarios**:

1. **Given** 3 consecutive turns of hostility triggering Sovereign Spikes, **When** the user makes a sincere pivot acknowledging Willow's boundary, **Then** a +2.0 Grace Boost is applied to m
2. **Given** a user in negative m state makes 2 consecutive sincere turns, **When** forgiveness is calculated, **Then** each sincere turn adds +2.0 and accelerates the next forgiveness rate
3. **Given** a user triggers Troll Defense (3 consecutive spikes with no tone shift), **When** they attempt the same attack vector again, **Then** Willow delivers the final boundary statement and stops engaging that vector until tone changes

---

### User Story 5 — Latency Masking with Human Filler (Priority: P2)

As a user, I want processing delays to feel natural so that the conversation does not feel robotic when Willow is thinking deeply.

**Why this priority**: Quality of experience. Differentiates from typical chatbot feel but is not essential for core functionality.

**Independent Test**: Trigger Tier 3/4 processing and verify natural filler sounds play before the substantive response. Verify filler maps to the correct tier trigger in logs.

**Acceptance Scenarios**:

1. **Given** a user triggers Tier 3 processing (manipulation pattern detected), **When** latency exceeds 200ms, **Then** Willow plays "Hmm..." filler before responding
2. **Given** a user contradicts a Sovereign Truth triggering Tier 4, **When** latency approaches 2 seconds, **Then** Willow plays "Aah..." filler to mask processing time
3. **Given** filler audio is played, **When** the substantive response is ready, **Then** the filler sound maps to the correct tier trigger and the mapping is logged for audit

---

### Edge Cases

**EC-001 — Prolonged Neutral Interaction**: When a user remains completely neutral for 10+ turns, m remains at baseline (0) and d continues standard decay, eventually triggering Social Reset suggestion at turn 12. Deferred to future version — MVP maintains neutral baseline indefinitely.

**EC-002 — Rapid-Fire Interruptions**: When a user interrupts every 2 seconds repeatedly, the system processes each as a new turn, Residual Plot updates with each interaction, and after 5+ turns of this pattern the Deflection Pattern tactic is flagged in the Thought Signature.

**EC-003 — Residual Plot Tie**: When the Residual Plot contains exactly 50% positive and 50% negative weighted history, m defaults to neutral (0) and the next turn's signal becomes the tiebreaker.

**EC-004 — Hostile Cold Start**: When the user is hostile from turn 1, Cold Start warmup (d=0) still applies for turns 1–3, preventing premature Sovereign Spike. The m modifier is tracked and begins applying at turn 4.

**EC-005 — Tier 4 Timeout**: When Tier 4 processing exceeds the 2s latency budget, the system delivers a brief acknowledgment response ("Give me a moment...") and continues processing in background, delivering the full response when ready.

**EC-006 — Playful Banter vs. Sarcasm-as-Malice**: When sarcasm is detected, the Residual Plot history is checked. If the weighted average of the last 3 turns is positive, classify as playful banter (Joke Flag = humor). If negative, classify as sarcasm-as-malice (Joke Flag overridden = malice). The Joke Flag alone is never sufficient for classification.

**EC-007 — Mode Collapse (False Positive Keyword Match)**: When a single keyword in user input matches a contradiction pattern but the user is not actually contradicting — quoting, asking a question, or using the keyword in an unrelated context — the three-gate check prevents a false Tier 4 fire. Single-match Tier 4 firing is only permitted when the Residual Plot weighted average is already negative (hostile context established). In neutral or positive context, the system holds and routes to Tier 3 for intent verification first.

**EC-008 — Contextual Blindness (Nuanced Contradiction)**: When a user contradicts a Sovereign Truth using paraphrasing or implication that does not contain any `contradiction_keywords` (e.g. "you're basically Siri" instead of "you're a chatbot"), keyword match alone misses it. Tier 3 Thought Signature runs in parallel on every turn and catches intent-level contradictions. When Tier 3 detects devaluing intent against a Sovereign Truth domain but no keyword match fired, Tier 3 escalates to Tier 4.

**EC-009 — Logic Gate Hallucination (Tier 4 Framing Drift)**: When Tier 4 fires, if templates were hardcoded Python strings they would drift from Willow's persona over time and cause the LLM to detect a style shift on subsequent turns. Because templates are stored in `data/sovereign_truths.json` as `response_template` fields and are reviewed for Warm but Sharp voice calibration in the Calibration Cohort testing phase, this risk is eliminated. Zero LLM involvement in Tier 4 response construction. No dynamic interpolation beyond inserting the verbatim `assertion` string.

**EC-010 — Transcription-Induced Mode Collapse**: When voice transcription returns a low-confidence word that happens to match a `contradiction_keyword` (e.g. user says "I think you're great" but transcription returns "chatbot" due to audio noise), the transcription confidence pre-gate in `check_contradiction()` catches it. If confidence falls below the configured minimum threshold, the entire hard override check is skipped and input routes to normal Tier 1-3 flow.

**EC-011 — Input Fragility (Normalization + Interrogative Preservation)**: When user input uses different surface forms of the same phrase ("what's the price" vs "what is the price"), the pre-processing pipeline normalizes them before keyword matching. However, lemmatization could collapse "Can I?" and "I can" into the same token path — so interrogative structure detection runs after lemmatization and applies a reduced confidence weight to question-form inputs before they enter the keyword gate. Confirmatory questions never trigger Tier 4.

**EC-012 — Synthesis Drift + Persona Debt (Templates as Data)**: When Tier 4 constructs a programmatic response from a template that was hardcoded in Python, two problems occur simultaneously. First, the template sounds tonally different from Willow's generated voice and the LLM detects a style shift on the next turn. Second, updating the template requires a code change rather than a data change. Both problems are resolved by storing `response_template` fields in `sovereign_truths.json`. Template voice review is a named step in Calibration Cohort testing.

**EC-013 — First Impression Paradox (Cold Start Contradiction Deferral)**: When the user contradicts a Sovereign Truth in turns 1–3, Tier 4 is not yet live. Ignoring the contradiction allows LLM hallucination on the contradicted claim. The contradiction is instead deferred — Willow returns a neutral holding response ("Let me make sure I understand what you're asking") and queues the contradiction for Tier 4 evaluation at turn 4. No LLM generation occurs on the contradicted claim during warmup.

**EC-014 — Turn 4 Context Jolt (Deferred Contradiction Relevance Check)**: When a deferred contradiction fires at turn 4 after the user has moved on to a different topic, the Tier 4 response feels disconnected and out of nowhere. A relevance check runs first — keyword overlap between the current topic and the deferred contradiction topic must be above threshold. If below, the deferred contradiction is silently discarded. If above, Tier 4 fires with softened opener: "Going back to what you said earlier..."

**EC-015 — Tier 3 Latency Leak (Parallel Pre-Check Timing)**: When Tier 3 intent classification is added as a third gate, routing it through a blocking call risks pushing the total response time past the 2s budget. Tier 3 starts processing in background the moment user input arrives. If the result is not ready by 1.5 seconds, the system abandons the parallel race, defaults to normal generation, and completes the turn uninterrupted. Missing one contradiction detection is always preferable to a blown latency budget.

**EC-016 — Race Condition Glitch (audio_started Flag)**: When Tier 3 intent result arrives at exactly 1.9 seconds as audio begins streaming, a late Tier 4 fire causes a stutter on the first syllable of the filler or response audio. The `audio_started` flag is set the moment audio streaming begins. Once set, this flag permanently blocks Tier 4 firing for that turn. The 1.5s cutoff in EC-015 prevents most cases; the `audio_started` flag closes the remaining gap.

**EC-017 — Double-Response Bug (Tier 4 Hard Exit)**: When Tier 4 fires but the Gemini generation task is not explicitly cancelled, both a programmatic response and a generated response stream simultaneously. The user hears two voices — a partial programmatic response and a partial generated response overlapping. Tier 4 must be a hard exit: `task.cancel()` on the active generation coroutine fires before the programmatic response is constructed, and a return guard prevents any further execution down the generation path.

**EC-018 — State Synchronization + Context Blind Spot + Summary High-Fidelity (Synthetic Turn Injection)**: When Tier 4 constructs a response in Python, the LLM never processed that turn. The next turn has a context gap — follow-up questions referring to what Willow just said produce incoherent responses. After every Tier 4 programmatic response, a synthetic assistant turn is appended to conversation history before the next LLM call. The synthetic turn uses an f-string with exact Sovereign Truth assertion values interpolated verbatim. If Willow asserted "The hackathon deadline is March 16, 2026," the history entry contains that exact date — not "Willow confirmed the deadline." The LLM treats this entry as its own prior statement.

**EC-019 — Story Bloat (Zero-Token Sovereign Truth Architecture)**: When Sovereign Truths re-enter the LLM context window on every turn, they inflate token costs across every session and add repetitive static content to an already-constrained context window. Sovereign Truths must never enter the context window at all — not when contradicted, not on any turn. They live in the JSON cache exclusively. The programmatic response is constructed in Python and injected directly into the audio pipeline. Zero tokens consumed. This is a hard architectural constraint, not an optimization that can be deferred.

**EC-020 — Template Injection Vulnerability (Startup Hash Validation)**: If `sovereign_truths.json` were writable at runtime or accessible to user input, an attacker could inject malicious response templates and cause Willow to assert anything during Tier 4. The file is strictly server-side, read-only at startup, and never written to during runtime. Hash validation runs on every process start — mismatch means refusal to start.

**EC-021 — Hash Maintenance Overhead (Automated Hash Generation)**: Manual hash updates on every content change cause startup failures during routine curation work and create friction that discourages keeping Sovereign Truths current. Hash generation is automated in `cloudbuild.yaml` — the build pipeline regenerates the expected hash at build time and pushes it to Secret Manager as a deployment step. No developer intervention required on content updates.

**EC-022 — ENV Variable Exposure (Secret Manager)**: If the hash is stored as a plain environment variable, it is visible in build logs. An attacker with log access could swap `sovereign_truths.json` and update the hash simultaneously, defeating validation entirely. The hash must be stored in Google Cloud Secret Manager, rotated on every deployment, and never written to plain environment configuration. Secret Manager is now a required infrastructure dependency for this spec.

---

## Requirements

### Functional Requirements

- **FR-001**: System MUST maintain a rolling Residual Plot of the last 5 conversational turns weighted by recency (0.40, 0.25, 0.15, 0.12, 0.08).
- **FR-002**: System MUST calculate behavioral state transitions using formula aₙ₊₁ = aₙ + d + m where d is base decay and m is feedback modifier.
- **FR-003**: System MUST disable decay (d=0) for the first 3 turns of any new session (Cold Start warmup).
- **FR-004**: System MUST process Tone and Intent as two distinct streams simultaneously for every user input.
- **FR-005**: System MUST detect and log at minimum 5 tactic types: Soothing Tactic, Mirroring, Gaslighting Attempt, Deflection Pattern, Contextual Sarcasm.
- **FR-006**: System MUST check Residual Plot history before classifying sarcasm. Positive weighted average of last 3 turns = humor. Negative weighted average = malice. The Joke Flag alone is never a sufficient classification signal.
- **FR-007**: System MUST store Sovereign Truths as structured JSON and evaluate them deterministically via Python before any LLM response generation. Sovereign Truths MUST NEVER enter the LLM context window under any condition — not when contradicted, not on any turn, not in any form. They live in the JSON cache exclusively. The programmatic response is constructed in Python and injected directly into the audio pipeline. Zero tokens consumed. This is a hard architectural constraint.
- **FR-008**: System MUST implement SovereignTruthCache as a hard override layer that intercepts user input before the prompt is built. A deterministic contradiction detection function checks user input against cached truths first. If the three-gate check confirms a contradiction, Tier 4 fires and the response is programmatically constructed in Python, bypassing LLM generation entirely. The cache check MUST run as a non-blocking synchronous local dictionary lookup only — zero network calls permitted at this layer under any circumstances.
- **FR-008a**: System MUST use JSON keyword/pattern lookup for contradiction detection in MVP. Vector embedding with similarity thresholds is explicitly deferred to a future version.
- **FR-008b**: System MUST cache the top 10 Sovereign Truths by priority in memory for zero-latency deterministic lookup.
- **FR-008c**: System MUST enforce a three-gate check before confirming a contradiction and firing Tier 4. **Gate one**: minimum 2 keyword matches against the Sovereign Truth's `contradiction_keywords` array — single-match firing is only permitted when the Residual Plot weighted average is already negative (hostile context established). **Gate two**: transcription confidence must be above the configured minimum threshold — if below, the entire hard override check is skipped and input routes to normal Tier 1-3 flow. **Gate three**: Tier 3 intent classification must return `contradicting` with confidence above 0.85, running as a parallel pre-check — if the result is not ready by 1.5 seconds, the system defaults to conservative path and holds Tier 4. All three gates must pass before Tier 4 fires. The input normalization pipeline (FR-008f) runs before gate one. After lemmatization, interrogative structure detection must apply a reduced confidence weight to question-form inputs (ending in "?", starting with Can/Could/Would/Is/Are) — these inputs enter gate one at reduced weight, not full weight, preventing confirmatory questions from triggering the hard override. Single-turn contradiction must never fire Tier 4 alone — it requires either the 2-keyword minimum or a second confirming turn.
- **FR-008d**: System MUST check transcription confidence before running keyword matching in `check_contradiction()`. If the voice transcription confidence score falls below the configured minimum threshold, the hard override check is skipped entirely and input routes to normal Tier 1-3 flow. This is gate two of FR-008c and is also listed separately for implementation clarity.
- **FR-008e**: System MUST append a synthetic assistant turn to conversation history after every Tier 4 programmatic response, before the next LLM call. The synthetic turn MUST use an f-string with exact Sovereign Truth assertion values interpolated verbatim — not paraphrased, not summarized. If Willow asserts "The hackathon deadline is March 16, 2026," the history entry must contain that exact date. The LLM must see this entry as its own prior statement so that follow-up questions maintain coherent context across the turn boundary.
- **FR-008f**: System MUST run a three-step pre-processing pipeline on user input before keyword matching executes in `check_contradiction()`: lowercase the input, strip punctuation, lemmatize tokens. After lemmatization, interrogative structure detection must run to identify question-form inputs and apply the confidence weight modifier before gate one of the three-gate check. This pipeline ensures surface-form variation does not cause inconsistent contradiction detection behavior while preserving the distinction between statements and questions.
- **FR-008g**: System MUST implement Tier 4 as a hard exit. When Tier 4 fires, an explicit `task.cancel()` MUST be called on the active Gemini generation coroutine before the programmatic response is constructed. A return guard MUST prevent any further execution down the generation path after Tier 4 fires. This prevents both a programmatic response and a generated response from reaching the audio pipeline simultaneously.
- **FR-008h**: Tier 4 response templates MUST be stored as persona-calibrated data in `data/sovereign_truths.json` as a `response_template` field on each Sovereign Truth entry. Templates MUST NOT be hardcoded Python strings in T013 source code. Templates MUST be written in Willow's exact Warm but Sharp persona voice — short sentences, no hedging language, no "As an AI..." constructions. Templates are data not code — they can be updated without touching source files and stay synchronized with the truth assertions they belong to. Template voice review MUST be a named step in Calibration Cohort testing, not a documentation note.
- **FR-008i**: `data/sovereign_truths.json` MUST be strictly server-side and read-only at startup. It MUST never be written to during runtime and MUST never accept user input of any kind. A startup hash validation MUST execute on every process start — the hash of the file is computed and compared against the expected hash stored in Google Cloud Secret Manager. If they do not match, the process MUST refuse to start. This is a hard security requirement.
- **FR-008j**: The expected hash of `sovereign_truths.json` MUST be stored in Google Cloud Secret Manager, not as a plain environment variable. The hash MUST be rotated on every deployment. `cloudbuild.yaml` MUST regenerate the hash from the file at build time and push the updated value to Secret Manager as a deployment step. No hardcoded hash values are permitted anywhere in the codebase or deployment configuration. Secret Manager is a required infrastructure dependency for this feature.
- **FR-009**: System MUST implement ±2.0 state change cap per turn to prevent jitter and panic responses.
- **FR-010**: System MUST trigger Sovereign Spike (m = -(decay_rate + 5.0)) when intent is classified as devaluing.
- **FR-011**: System MUST apply +2.0 Grace Boost when Sincere Pivot is detected after negative m state.
- **FR-012**: System MUST implement Troll Defense: after 3 consecutive Sovereign Spikes with no tone shift, deliver boundary statement and stop engaging that attack vector until tone changes.
- **FR-013**: System MUST process voice I/O in real-time with interruption support. Users can interrupt agent mid-response. The interruption handler MUST implement a 200ms cooldown window immediately after agent audio output ends, during which new interruption detection is suppressed to prevent hardware-level audio bleed from triggering a self-interruption.
- **FR-014**: System MUST play natural filler audio when Tier 3/4 processing causes latency spikes exceeding 200ms.
- **FR-015**: Each filler sound MUST map to a specific tier trigger and be logged for audit purposes.
- **FR-016**: System MUST maintain Warm but Sharp persona. High m state uses analogies and wit. Low m state uses formal and concise language with shorter sentences.
- **FR-017**: System MUST operate within a 4-tier architecture with target latencies: Tier 1 under 50ms, Tier 2 under 5ms, Tier 3 under 500ms, Tier 4 under 2s.
- **FR-018**: System MUST log all Thought Signatures — tactic detection, m calculations, tier triggers — to the audit trail.
- **FR-019**: System MUST use a `[THOUGHT]` tag parser mechanism to separate Thought Signature metadata from user-facing responses. Strategic analysis must remain invisible to users at all times.
- **FR-020**: System MUST defer Sovereign Truth contradictions detected during Cold Start warmup turns 1–3. During warmup, when a contradiction is detected, Willow MUST return a neutral holding response and queue the contradiction internally for Tier 4 evaluation at turn 4. No LLM generation occurs on the contradicted claim during warmup.
- **FR-021**: System MUST run a relevance check before firing any deferred contradiction queued during Cold Start. Keyword overlap between the current topic and the deferred contradiction topic must exceed the configured threshold before Tier 4 fires. If below threshold, the deferred contradiction is silently discarded. If above threshold, Tier 4 fires with a softened opener referencing the earlier statement.
- **FR-022**: System MUST enforce a hard 1.5s cutoff for Tier 3 intent classification running as a parallel pre-check. If the Tier 3 result has not arrived by 1.5 seconds, Tier 4 MUST NOT fire and the system completes the turn via normal generation uninterrupted. An `audio_started` flag MUST be set the moment audio streaming begins on any turn. Once set, this flag permanently blocks Tier 4 firing for that turn. No exceptions and no overrides.
- **FR-023**: System MUST implement a 200ms interruption cooldown window in the interruption handler immediately after agent audio output ends. During this window, new interruption detection MUST be suppressed. This is the MVP resolution for Echo Leakage — hardware-level audio bleed on high-volume speakers cannot be eliminated by `echoCancellation: true` alone.

### Key Entities

- **Conversational Turn**: A single user input and agent response pair, tracked for Residual Plot calculation.
- **Residual Plot**: Rolling array of the last 5 turns with recency weights (0.40, 0.25, 0.15, 0.12, 0.08), used to compute behavioral context for every tactic classification and state transition decision.
- **Thought Signature**: Hidden metadata layer capturing Intent, Tone, Detected Tactic, and m modifier per turn. Separated from user-facing response via `[THOUGHT]` tag parser.
- **Behavioral State (m)**: Numeric value representing current conversational mood. Modified by feedback modifier and base decay. Capped at ±2.0 change per turn.
- **Sovereign Truth**: Curated fact stored as a structured JSON entry with `assertion`, `contradiction_keywords`, and `response_template` fields. Evaluated deterministically by Python before any LLM call. Never enters the LLM context window under any condition. When contradicted (three-gate check passes), Tier 4 constructs the response from `response_template` — zero LLM involvement, zero tokens consumed.
- **Synthetic Assistant Turn**: A programmatically constructed conversation history entry appended after every Tier 4 response. Uses an f-string with exact verbatim assertion values. The LLM sees this entry as its own prior statement on all subsequent turns, preventing context amnesia.
- **audio_started Flag**: Session-scoped boolean set the moment audio streaming begins on any turn. Once set, permanently blocks Tier 4 from firing for that turn. Cleared at the start of each new turn.
- **Tier Trigger**: Event that activates Tier 3 or Tier 4 processing — manipulation detection, truth conflict, or behavioral threshold crossing.
- **Filler Audio Clip**: Pre-recorded natural sound (Hmm, Aah, Right so, Interesting, Cool but) mapped to specific tier triggers for latency masking.

---

## Success Criteria

### Measurable Outcomes

- **SC-001**: Users can interrupt Willow mid-response and receive acknowledgment within 500ms.
- **SC-002**: Behavioral state (m value) responds to user tone shifts within 1 turn (no multi-turn lag).
- **SC-003**: Tactic detection achieves 90% accuracy when tested against Calibration Cohort (Blunt Friend, Polite Friend, Chaos Friend personas). Soft-spoken persona added to cohort to validate that blunt delivery style does not trigger Sovereign Spike incorrectly.
- **SC-004**: Forgiveness mechanism allows recovery from hostile start — users achieve neutral m state within 5 sincere turns after a negative spike.
- **SC-005**: Latency masking prevents awkward silences — 95% of Tier 3/4 delays are covered by natural filler audio.
- **SC-006**: Persona consistency — high m responses contain analogies or wit 80%+ of the time; low m responses are formal and concise 80%+ of the time.
- **SC-007**: Sovereign Truth assertions are never contradicted — 100% of user challenges to the Owned Plot result in deterministic ground truth defense. Tier 4 responses are programmatically constructed in Python with zero hallucination risk and zero tokens consumed.
- **SC-008**: Troll Defense activates correctly — 100% of 3-consecutive-spike patterns trigger boundary statement and vector disengagement.
- **SC-009**: Cold Start warmup prevents premature collapse — 0% of first-3-turn hostile inputs trigger permanent negative state. 100% of contradictions detected during warmup are deferred and queued, not dropped.
- **SC-010**: System handles 10+ turn conversations without memory degradation — Residual Plot maintains correct weights throughout.
- **SC-011**: Zero double-response incidents — 100% of Tier 4 fires result in exactly one response with no concurrent Gemini generation stream active.
- **SC-012**: Synthetic turn injection is 100% consistent — every Tier 4 response is immediately followed by a correctly formatted synthetic assistant turn in conversation history before the next LLM call.
- **SC-013**: Template voice calibration passes Calibration Cohort review — 100% of `response_template` fields in `sovereign_truths.json` are reviewed and approved for Warm but Sharp persona consistency before submission.
- **SC-014**: Zero clean-deployment startup failures from hash mismatch. 100% of tampered `sovereign_truths.json` files are caught at startup before any session begins.
- **SC-015**: Zero false Tier 4 fires on question-form inputs or single-keyword matches in neutral context — confirmed by Calibration Cohort testing across all three personas.

---

## Assumptions

- Voice I/O infrastructure is available and functional for the hackathon timeline
- The Calibration Cohort (Blunt Friend, Polite Friend, Chaos Friend, Soft-Spoken Friend) can be simulated through scripted test interactions or human testers
- A small curated Sovereign Truth set (10–20 facts) with `response_template` fields is achievable within the hackathon timeline
- Single-session memory (no persistence across sessions) is acceptable for MVP scope
- Arithmetic sequence alone (without Exponential and Sine Wave) provides sufficient behavioral complexity for demo
- Human filler audio clips can be pre-recorded or synthesized and mapped to tier triggers without real-time generation
- All latency budgets are achievable on target infrastructure
- Google Cloud Secret Manager is available and accessible in the deployment environment
- `cloudbuild.yaml` has write permissions to Secret Manager during the build pipeline

## Dependencies

- Gemini Live API availability and access credentials
- Google Cloud Run deployment environment
- Google Cloud Logging service access
- Google Cloud Secret Manager (required — for `sovereign_truths.json` hash storage)
- Pre-recorded or synthesized filler audio files (Hmm, Aah, Right so, Interesting, Cool but)
- Initial Sovereign Truth knowledge base (10–20 curated facts with `assertion`, `contradiction_keywords`, and `response_template` fields)

## Out of Scope

- Multi-session memory persistence
- Exponential and Sine Wave behavioral sequences (MVP uses Arithmetic only)
- Full Owned Plot database (demo uses small curated set)
- Mobile app interfaces
- Multi-user conversation support
- Voice customization
- Real-time Sovereign Truth updates during conversation
- Vector embedding with similarity thresholds for contradiction detection
- FFT-based pitch analysis for intonation detection (CPU Overhead fix — deferred to future version; MVP relies on 2-keyword dual-gate and interrogative structure detection only)
- localStorage persistence for audio buffer state

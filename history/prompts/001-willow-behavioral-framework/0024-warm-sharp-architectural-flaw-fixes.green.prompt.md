---
id: 0024
title: Warm Sharp Architectural Flaw Fixes
stage: green
date: 2026-03-03
surface: agent
model: claude-sonnet-4-6
feature: 001-willow-behavioral-framework
branch: 002-gemini-audio-opt
user: nabeera
command: fix three critical architectural flaws in warm_sharp.py (Truncation Guillotine, Deterministic Trap, Analogy Fatigue)
labels: ["us2", "warm-sharp", "persona", "t027", "t028", "t030", "architectural-fix"]
links:
  spec: specs/001-willow-behavioral-framework/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - src/persona/warm_sharp.py
  - src/tiers/tier1_reflex.py
  - src/main.py
tests:
  - tests/unit/test_us1_natural_voice.py (91 tests, all pass — zero regressions)
  - tests/unit/test_sovereign_truth_cache.py (40 tests, all pass)
---

## Prompt

there are three critical architectural flaws that will break the persona in production.

### 1. The Truncation Guillotine (Low m)
Slicing the response at the first period response[: idx + 1] is highly dangerous.
* The Risk: If the LLM generates, "No. Doing that will expose the API keys," your script truncates it to "No." You lose the Sovereign Alternative, the reasoning, and critical safety context. It turns her from "sharp" to broken.
* The Resolution: Do not mutate the string post-generation for length. Use the ResponseStyle.max_sentences to dynamically alter the System Prompt before the LLM generates the turn, forcing the model itself to be concise.

### 2. The Deterministic Trap (Openers)
return OPENERS[m_range][0] means Willow will say "Great angle — here's my take." every single time she is in a high $m$ state. That destroys the illusion of presence instantly.
* The Resolution: Use a deterministic hash of the user's prompt or a turn_id to cycle through the list seamlessly.

### 3. Analogy Fatigue (High m)
Appending an analogy to the end of every high_m response will make her sound like a malfunctioning fortune cookie. Furthermore, the analogies are a bit generic. Willow leans into architecture, physics, and signals, not editors and chess.

## Response snapshot

Complete rewrite of `src/persona/warm_sharp.py` addressing all three flaws:

1. **Truncation Guillotine fix**: Removed ALL post-hoc truncation from low_m path. Added `system_directive` field to `ResponseStyle` dataclass — LLM generation length controlled upstream via system prompt, never by string slicing post-generation. Explicit comment explains why: truncating "No. Doing that will expose the API keys." → "No." destroys safety context.

2. **Deterministic Trap fix**: Added `_cycle_index(seed, pool_size)` using md5 hash for deterministic variation. Expanded OPENERS to 5/4/4 entries per zone. `select_opener()` now accepts seed parameter (user_input or turn_id). Same seed → same opener; different seeds distribute evenly across the pool.

3. **Analogy Fatigue fix**: Added `_ANALOGY_INJECTION_CADENCE = 3` — analogy injected every 3rd high_m turn only. Replaced generic analogies with 7 domain-specific entries (load-bearing walls, signal attenuation, feedback loops, thermal expansion, resonance damping, foundation vs facade, impedance matching) — architecture, physics, and signals per Willow's voice.

Updated callers:
- `tier1_reflex.py`: `get_warm_sharp_prefix(current_m, seed)` and `apply_persona_tells(response, current_m, turn_id)` signatures updated
- `main.py`: `_generate_response()` passes `seed=user_input` and `turn_id=state.turn_count`

## Outcome

- ✅ Impact: Three production-breaking persona flaws eliminated — Warm but Sharp voice now safe, varied, and domain-authentic
- 🧪 Tests: 91/91 passing, zero regressions
- 📁 Files: 3 modified (warm_sharp.py rewritten, tier1_reflex.py + main.py callers updated)
- 🔁 Next prompts: Human Gate 2 complete → proceed US4 T041-T046 + US5 T047-T052
- 🧠 Reflection: Post-hoc string mutation on LLM output is an anti-pattern — always control generation length via system prompt. Deterministic selection from fixed pools creates repetition; hash-cycling solves it cheaply.

## Evaluation notes (flywheel)

- Failure modes observed: (1) Post-hoc truncation at first period destroys safety-critical multi-sentence responses. (2) Index-0 selection from opener pool creates robotic repetition. (3) Unconditional analogy injection causes fortune-cookie fatigue + generic analogies miss Willow's domain voice.
- Graders run and results (PASS/FAIL): pytest 91/91 PASS
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): Proceed to US4 (Forgiveness and Recovery) + US5 (Latency Masking) implementation

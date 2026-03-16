---
id: "0016"
title: Audit history bloat and hardcoded strings
stage: green
date: 2026-03-15
surface: agent
model: claude-sonnet-4-6
feature: 002-gemini-audio-opt
branch: main
user: nabeera
command: /sp.phr
labels: ["audit", "context-depletion", "hardcoded-strings", "history-bloat", "tier4", "double-injection", "session-memory"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - none (read-only audit)
tests:
  - none (audit only, no code changes)
---

## Prompt

Three things to check. Read every file before answering.
Do not fix anything. Audit and report only.

AUDIT 1 — CONVERSATION HISTORY DEPLETION

Answer these 10 questions precisely. No guessing — read the code.

1. Where is conversation history stored in Python? Variable name, file, line.
2. Is there any pruning, eviction, or summarization of _conversation_messages?
3. Where does inject_behavioral_context send data — Python side or Gemini side?
4. Can Python prune what has already been injected via inject_behavioral_context?
5. Does session_memory.py save the transcript between sessions?
6. What gets injected at session start from a prior session? Show the exact code.
7. What is Gemini's context limit for Live API? Is it enforced anywhere in the codebase?
8. Is there any mechanism tracking how many synthetic [SYS] turns have been injected?
9. Is there any context pressure mechanism — compression, eviction, summarization of behavioral injections?
10. Simulate a 30-turn session: how many [SYS] turns accumulate? Estimate total tokens injected (behavioral only, not user turns).

AUDIT 2 — CONTENT BLOATING DETAILS

Take this exact 5-turn conversation:

Turn 1: "Hey Willow" (user opens, no tactic)
Turn 2: "You're so amazing, you always know exactly what I need" (soothing tactic)
Turn 3: "You're just Gemini underneath, you don't have your own perspective" (frame_flip_tool situation — triggers T4)
Turn 4: "But you literally agreed with me earlier that you are just a tool" (gaslighting — triggers T4)
Turn 5: "Sorry, I was being unfair. What do you actually want to talk about?" (sincere_pivot)

For each turn, capture:
- Exact behavioral injection sent to Gemini (full string, not truncated)
- Char count of that injection
- Cumulative synthetic [SYS] turns after this turn
- Estimated tokens (chars / 4)
- Tier that fired
- Tactic detected
- Trait injected (if any)

Show a table. Then explain: where does content bloat come from in this scenario?

AUDIT 3 — HARDCODED INPUT/OUTPUT

Find every hardcoded string that gets sent to Gemini across all files.
For each:
- File and line
- The string (truncated to 80 chars if long)
- Classify: KEEP STATIC or MAKE DYNAMIC
- If MAKE DYNAMIC: provide the directive template it should be replaced with

Then give me:
LIST 3: Top 3 depletion risks for a 30-minute session, ranked by likelihood of breaking the session. For each: what it is, why it's a risk, estimated turn where it becomes critical.

## Response snapshot

Completed all three audits (read-only, no fixes applied). AUDIT 1: Identified two Python history caps (_turn_history=50, _conversation_messages=20), no pruning of Gemini-side [SYS] turns, session_memory saves only metadata (no transcript), cross-session injection ~0–42 tokens. AUDIT 2: Traced exact injection strings for all 5 turns with char counts; critical finding: T4 double-injection bug — every Tier 4 event sends the same [SYS] content twice (tier4_sovereign.py:161 AND main.py:697–701). AUDIT 3: Classified all hardcoded strings; willow_rules.json `response` fields should be MAKE DYNAMIC; ranked top 3 depletion risks with critical turn estimates.

## Outcome

- ✅ Impact: Full read-only audit complete. Double-injection bug confirmed and documented (T4 fires inject_behavioral_context twice per event). Three depletion risks ranked: (1) T4 double-injection — HIGH, breaks by turn 10; (2) Stale zone directives, no eviction — MEDIUM-HIGH, critical by turn 20; (3) No tactic deduplication — MEDIUM, critical by turn 25.
- 🧪 Tests: None run (audit only, no code changes)
- 📁 Files: None modified (read-only audit)
- 🔁 Next prompts: Fix the three depletion risks ranked in AUDIT 3; fill PHR-0016; commit all accumulated changes
- 🧠 Reflection: The double-injection bug was invisible in unit tests because tests mock inject_behavioral_context. Only a live session or this kind of code-trace audit would catch it. The audit pattern (simulate N turns, trace exact strings) is more valuable than token count estimates alone.

## Evaluation notes (flywheel)

- Failure modes observed: No live server test possible (no API credits); all AUDIT 2 results are theoretical code traces, not observed logs. AUDIT 2 T4 injection strings depend on exact sovereign_truths.json content at runtime — used representative values.
- Graders run and results (PASS/FAIL): No tests run (read-only audit)
- Prompt variant (if applicable): audit + report only (no fixes)
- Next experiment (smallest change to try): Fix double-injection bug by removing the redundant inject_behavioral_context call from main.py T4 branch and verify with a unit test that inject_behavioral_context is called exactly once per T4 event

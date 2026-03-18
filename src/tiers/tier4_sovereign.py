"""
Tier 4: The Sovereign — T035

Hard override layer. When all three gates pass, cancels the active Gemini
generation coroutine and delivers a deterministic, LLM-free response.

Execution sequence (FR-008g, FR-008h, FR-008e, FR-022):
1. Interrupt active Gemini generation via streaming_session.interrupt() (FR-008g).
2. Check truth.vacuum_mode:
   - True:  suppress all speech output; play acoustic heartbeat only;
            store truth.response_on_return on SessionState for delivery
            on the next utility signal. Skip steps 3-5.
   - False: continue.
3. Read response_template from the matching SovereignTruth and build
   response with verbatim assertion interpolation only (FR-008h).
4. Inject response into audio pipeline — zero LLM tokens consumed.
   Sovereign Truths NEVER enter the LLM context window (FR-007).
5. Append synthetic assistant turn with exact verbatim assertion to
   conversation history (FR-008e).
6. Set audio_started flag to block late Tier 4 re-fires for this turn (FR-022).

Target latency: <2 000ms.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Final, Optional

from ..core.sovereign_truth import SovereignTruth, SovereignTruthCache, MIN_TRANSCRIPTION_CONFIDENCE
from ..core.state_manager import StateManager
from .tier_trigger import TierTrigger
from ..voice.gemini_live import StreamingSession

logger = logging.getLogger(__name__)

TIER4_LATENCY_BUDGET_MS: Final[float] = 2_000.0
FILLER_LATENCY_THRESHOLD_MS: Final[float] = 200.0  # T048 / US5


@dataclass
class Tier4Result:
    """
    Output of Tier 4 Sovereign processing.

    Attributes:
        fired: True when all three gates passed and the hard override executed.
        vacuum_mode: True when the matched truth used vacuum mode.
        forced_prefix: Exact words Willow must use to start her sentence.
        response_directive: Strict instruction to the LLM on how to finish the sentence.
        synthetic_turn: Dict appended to conversation history, or None
            when vacuum_mode is True.
        audio_started_set: True when set_audio_started() was called.
        flush_audio_buffer: True when the caller must send a flush command
            to the browser AudioWorklet to gracefully fade out any in-flight
            audio before delivering the sovereign response (T025, FR-010).
        latency_ms: Total processing time in milliseconds.
        within_budget: Whether processing completed within 2 000ms.
    """

    fired: bool
    vacuum_mode: bool
    forced_prefix: str
    response_directive: str
    synthetic_turn: Optional[dict]
    audio_started_set: bool
    flush_audio_buffer: bool
    latency_ms: float
    within_budget: bool
    tier_trigger: Optional[TierTrigger] = None  # T048: set when latency >200ms

    def to_dict(self) -> dict[str, Any]:
        return {
            "fired": self.fired,
            "vacuum_mode": self.vacuum_mode,
            "forced_prefix": self.forced_prefix,
            "response_directive": self.response_directive,
            "synthetic_turn": self.synthetic_turn,
            "audio_started_set": self.audio_started_set,
            "flush_audio_buffer": self.flush_audio_buffer,
            "latency_ms": self.latency_ms,
            "within_budget": self.within_budget,
        }


class Tier4Sovereign:
    """
    Tier 4: The Sovereign — deterministic hard override.

    Consumes SovereignTruthCache gate results and executes the override
    sequence without any LLM involvement. The caller (main.py) is
    responsible for:
      - Running the three-gate check (check_contradiction → run_gate_two
        → run_gate_three) before invoking execute().
      - Forwarding response_text to the audio pipeline.
      - Appending synthetic_turn to conversation history.

    Usage:
        tier4 = Tier4Sovereign(cache, state_manager)

        # After three-gate check passes:
        result = await tier4.execute(truth, streaming_session)
        if result.fired and not result.vacuum_mode:
            # Inject result.response_text into audio pipeline
            # Append result.synthetic_turn to conversation history
    """

    def __init__(
        self,
        cache: SovereignTruthCache,
        state_manager: StateManager,
    ) -> None:
        """
        Args:
            cache: Loaded SovereignTruthCache instance.
            state_manager: Active StateManager for flag manipulation.
        """
        self._cache = cache
        self._state_manager = state_manager

    async def execute(
        self,
        truth: SovereignTruth,
        streaming_session: Optional[StreamingSession] = None,
    ) -> Tier4Result:
        """
        Execute the full Tier 4 hard override sequence.

        Called only after all three gates have passed. See module docstring
        for the full execution sequence.

        Args:
            truth: The matching SovereignTruth from gate evaluation.
            streaming_session: The currently running StreamingSession,
                or None if no session is active.

        Returns:
            Tier4Result describing what was done.
        """
        start_ns = time.perf_counter_ns()

        # Step 1: Interrupt active Gemini generation (FR-008g / Q11 fix).
        # Replaces the dead-code hard_exit() path. We call interrupt()
        # directly on the streaming session to halt any in-progress audio.
        # THIS IS THE ONLY streaming_session call tier4_sovereign.py makes.
        # Behavioral context injection is main.py's sole responsibility —
        # tier4_sovereign.py returns forced_prefix + response_directive in
        # Tier4Result and never calls inject_behavioral_context() directly.
        if streaming_session is not None and streaming_session.is_connected:
            try:
                from ..voice.gemini_live import InterruptionReason
                await streaming_session.interrupt(reason=InterruptionReason.USER_SPEECH_DETECTED)
            except Exception as e:
                logger.warning("Tier 4 interrupt failed: %s", e)

        # Step 2: Vacuum mode branch
        if truth.vacuum_mode:
            # Suppress all speech; store response_on_return for next utility signal
            if truth.response_on_return is not None:
                await self._state_manager.set_response_on_return(
                    truth.response_on_return
                )

            # Set audio_started to block late Tier 4 re-fires for this turn (FR-022).
            # Even though vacuum mode produces no audio, Tier 4 has already fired.
            await self._state_manager.set_audio_started()

            latency_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
            within_budget = latency_ms < TIER4_LATENCY_BUDGET_MS

            logger.info(
                "Tier 4 vacuum mode: truth=%s response_on_return=%r latency=%.2fms",
                truth.key,
                truth.response_on_return,
                latency_ms,
            )

            # T048 / US5: Create TierTrigger for vacuum mode when latency exceeds 200ms
            from datetime import datetime as _dt
            vacuum_tier_trigger: Optional[TierTrigger] = None
            if latency_ms >= FILLER_LATENCY_THRESHOLD_MS:
                vacuum_tier_trigger = TierTrigger(
                    trigger_type="truth_conflict",
                    tier_fired=4,
                    filler_audio_played=None,
                    processing_duration_ms=latency_ms,
                    triggered_at=_dt.now(),
                )

            return Tier4Result(
                fired=True,
                vacuum_mode=True,
                forced_prefix="",
                response_directive="",
                synthetic_turn=None,
                audio_started_set=True,
                flush_audio_buffer=False,
                latency_ms=latency_ms,
                within_budget=within_budget,
                tier_trigger=vacuum_tier_trigger,
            )

        # Step 3: Extract forced_prefix and response_directive from truth (FR-008h)
        # Dynamic Determinism: LLM delivers response guided by sovereign constraints.

        # Step 4: (Caller injects into audio pipeline — zero LLM tokens, FR-007)

        # Step 5: Build synthetic assistant turn (FR-008e)
        synthetic_turn = SovereignTruthCache.build_synthetic_turn(truth)

        # Step 6: Set audio_started flag to block late re-fires (FR-022)
        await self._state_manager.set_audio_started()

        latency_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
        within_budget = latency_ms < TIER4_LATENCY_BUDGET_MS

        logger.info(
            "Tier 4 fired: truth=%s vacuum=False prefix=%r latency=%.2fms",
            truth.key,
            truth.forced_prefix[:60],
            latency_ms,
        )

        if not within_budget:
            logger.warning(
                "Tier 4 exceeded budget: %.2fms (budget: %.0fms)",
                latency_ms,
                TIER4_LATENCY_BUDGET_MS,
            )

        # T048 / US5: Create TierTrigger when latency exceeds 200ms.
        from datetime import datetime as _dt
        tier_trigger_record: Optional[TierTrigger] = None
        if latency_ms >= FILLER_LATENCY_THRESHOLD_MS:
            tier_trigger_record = TierTrigger(
                trigger_type="truth_conflict",
                tier_fired=4,
                filler_audio_played=None,  # main.py fills this in (T052)
                processing_duration_ms=latency_ms,
                triggered_at=_dt.now(),
            )

        return Tier4Result(
            fired=True,
            vacuum_mode=False,
            forced_prefix=truth.forced_prefix,
            response_directive=truth.response_directive,
            synthetic_turn=synthetic_turn,
            audio_started_set=True,
            flush_audio_buffer=True,
            latency_ms=latency_ms,
            within_budget=within_budget,
            tier_trigger=tier_trigger_record,
        )

    async def check_and_execute(
        self,
        user_input: str,
        transcription_confidence: float,
        weighted_average_m: float,
        tier3_intent_factory,
        streaming_session: Optional[StreamingSession] = None,
    ) -> Optional[Tier4Result]:
        """
        Run all three gates and execute if all pass.

        Convenience method combining the three-gate check with execute().

        Args:
            user_input: Raw user text.
            transcription_confidence: ASR confidence 0.0-1.0.
            weighted_average_m: Residual Plot weighted average.
            tier3_intent_factory: Zero-argument callable returning a coroutine
                that resolves to (intent: str, confidence: float). Called lazily
                — only invoked when gates 1 and 2 have passed.
            streaming_session: Active Gemini StreamingSession, or None.

        Returns:
            Tier4Result if all gates passed and override executed;
            None if any gate failed (normal flow resumes).
        """
        # Gate 1 + candidate lookup (transcription confidence + keyword match)
        candidate = self._cache.check_contradiction(user_input, transcription_confidence)

        # Write debug gate results to state
        state = self._state_manager.get_snapshot()
        gate_results = {}

        if candidate is None:
            gate_results["gate_1"] = {
                "passed": False,
                "asr_confidence": round(transcription_confidence, 2),
                "keyword_match": "NONE",
                "gate_1": "FAIL" if transcription_confidence < MIN_TRANSCRIPTION_CONFIDENCE else "NO TRIGGER",
            }
            state.last_gate_results = gate_results
            return None

        gate_results["gate_1"] = {
            "passed": True,
            "asr_confidence": round(transcription_confidence, 2),
            "keyword_match": candidate.key,
            "gate_1": "PASS",
        }
        state.last_sovereign_key = candidate.key
        state.last_transcription_confidence = transcription_confidence

        # Check preflight flag — skip Tier 4 entirely during warmup (T079, FR-013)
        if state.preflight_active:
            logger.debug("Tier 4 skipped: preflight_active=True")
            state.last_gate_results = gate_results
            return None

        # Check audio_started flag — block late fires for this turn (FR-022)
        if state.audio_started:
            logger.debug("Tier 4 skipped: audio_started=True for current turn")
            state.last_gate_results = gate_results
            return None

        # T076 / FR-020: Cold Start deferral — during turns 1-3, queue the
        # contradiction for evaluation at turn 4 instead of firing immediately.
        # This prevents premature Sovereign overrides before Willow has enough
        # conversational context (the "Social Handshake" window).
        if state.cold_start_active:
            await self._state_manager.queue_deferred_contradiction(
                truth_key=candidate.key,
                user_input=user_input,
                topic_keywords=candidate.contradiction_keywords,
            )
            logger.info(
                "Tier 4 deferred during Cold Start: truth=%s turn=%d",
                candidate.key,
                state.turn_count,
            )
            state.last_gate_results = gate_results
            return None

        # Gate 2: keyword count
        gate2_passed = self._cache.run_gate_two(candidate, user_input, weighted_average_m)
        gate_results["gate_2"] = {"passed": gate2_passed, "keyword_count": len(candidate.contradiction_keywords)}
        if not gate2_passed:
            state.last_gate_results = gate_results
            return None

        # Gate 3: Tier 3 intent confirmation (async, 1.5s cutoff).
        # Coroutine created lazily here — only after gates 1 and 2 pass.
        gate3_passed = await self._cache.run_gate_three(tier3_intent_factory())
        gate_results["gate_3"] = {"passed": gate3_passed, "confidence": 0.0}
        state.last_gate_results = gate_results

        if not gate3_passed:
            return None

        return await self.execute(candidate, streaming_session)

    async def evaluate_deferred_contradictions(
        self,
        current_user_input: str,
        streaming_session: Optional[StreamingSession] = None,
    ) -> Optional[Tier4Result]:
        """
        T076 / FR-021: Evaluate deferred contradictions at turn 4.

        Called from main.py when the Cold Start period ends (turn 4). Checks
        each deferred contradiction for topic relevance against the current
        user input. If relevant, fires with a softened opener. If not relevant,
        discards silently.

        Relevance is determined by keyword overlap between the deferred truth's
        topic_keywords and the current user input. This prevents stale
        contradictions from turns 1-3 from firing on unrelated turn 4 input.

        IMPORTANT: This method fires Tier 4 (a Sovereign override), NOT a
        grace boost. Deferred contradictions are factual corrections, not
        forgiveness events. The sincere_pivot / grace_boost path is entirely
        separate — it requires tactic detection of sincere_pivot, which a
        deferred contradiction evaluation does not produce.

        Args:
            current_user_input: The turn 4 user input for relevance check.
            streaming_session: Active Gemini StreamingSession, or None.

        Returns:
            Tier4Result if a relevant deferred contradiction was found and
            fired; None if all deferred contradictions were discarded.
        """
        deferred = await self._state_manager.consume_deferred_contradictions()
        if not deferred:
            return None

        normalized_input = self._cache._normalize_input(current_user_input)

        # Q28: Track the highest-priority unmatched truth so we can fire it
        # even if the user changed the subject. Sovereign Truths are factual
        # corrections that must be delivered — silently dropping them leaves
        # Willow complicit in misinformation.
        best_unmatched: Optional[SovereignTruth] = None

        for dc in deferred:
            # Relevance check: keyword overlap between deferred truth and current input
            overlap_count = sum(
                1
                for kw in dc.topic_keywords
                if self._cache._normalize_input(kw) in normalized_input
            )

            truth = self._cache.get(dc.truth_key)
            if truth is None:
                logger.warning(
                    "Deferred contradiction references missing truth: %s",
                    dc.truth_key,
                )
                continue

            if overlap_count > 0:
                # Relevant — fire immediately with the matched truth
                logger.info(
                    "Deferred contradiction fired (relevant at turn 4): truth=%s overlap=%d",
                    dc.truth_key,
                    overlap_count,
                )
                return await self.execute(truth, streaming_session)

            # Track highest-priority unmatched truth
            if best_unmatched is None or truth.priority > best_unmatched.priority:
                best_unmatched = truth

        # Q28: Fire the highest-priority deferred truth even without keyword
        # overlap. The user changed the subject, but the correction still needs
        # to be delivered. Willow will weave it in naturally via the forced_prefix.
        if best_unmatched is not None:
            logger.info(
                "Deferred contradiction fired (no keyword overlap, priority=%d): truth=%s",
                best_unmatched.priority,
                best_unmatched.key,
            )
            return await self.execute(best_unmatched, streaming_session)

        return None

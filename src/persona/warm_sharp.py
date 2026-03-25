"""
Warm but Sharp Persona — T027 + T030

Implements Willow's Warm but Sharp voice calibrated to behavioral state (m-value).
Templates cover three m-zones:
  - high_m  (current_m > 0.5): warmth, analogies, wit
  - neutral_m (-0.5 ≤ current_m ≤ 0.5): balanced, professional
  - low_m (current_m < -0.5): formal, concise, direct

Behavioral tells (T030):
  - Sentence length: high m → richer (controlled via system prompt directive,
    NOT post-hoc truncation); low m → system prompt instructs conciseness
  - Analogy injection: high m only, selective (not every turn), drawn from
    ANALOGY_POOL using domain-specific language (architecture, physics, signals)
  - Opener selection: hash-cycled from the pool using turn_id or user input
    to avoid repeating the same opener every turn

Per Constitution Principle I: Warm but Sharp — never cold, never a pushover.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Final, Literal

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _load_persona() -> dict:
    """Load willow_persona.json. Falls back to empty dict on failure."""
    persona_path = Path(__file__).parent.parent.parent / "data" / "willow_persona.json"
    try:
        with open(persona_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning("Failed to load willow_persona.json — using hardcoded defaults: %s", e)
        return {}

MRange = Literal["high_m", "neutral_m", "low_m"]

# m-value thresholds with hysteresis — asymmetric enter/exit prevents
# zone flapping on brief m spikes. Harder to enter a zone than to stay in it.
M_HIGH_THRESHOLD: Final[float] = 0.7   # legacy alias (entry)
M_LOW_THRESHOLD: Final[float] = -0.7   # legacy alias (entry)
M_HIGH_ENTER: Final[float] = 0.7
M_HIGH_EXIT: Final[float] = 0.3
M_LOW_ENTER: Final[float] = -0.7
M_LOW_EXIT: Final[float] = -0.3


def get_m_range(current_m: float, current_zone: MRange = "neutral_m") -> MRange:
    """Classify current_m into a behavioral zone with hysteresis.

    Uses asymmetric thresholds: entering a zone requires a stronger signal
    than staying in it. This prevents rapid zone flapping when m oscillates
    near a boundary.
    """
    if current_zone == "high_m":
        if current_m >= M_HIGH_EXIT:
            return "high_m"
        elif current_m <= M_LOW_ENTER:
            return "low_m"
        else:
            return "neutral_m"
    elif current_zone == "low_m":
        if current_m <= M_LOW_EXIT:
            return "low_m"
        elif current_m >= M_HIGH_ENTER:
            return "high_m"
        else:
            return "neutral_m"
    else:
        if current_m >= M_HIGH_ENTER:
            return "high_m"
        elif current_m <= M_LOW_ENTER:
            return "low_m"
        else:
            return "neutral_m"


# ---------------------------------------------------------------------------
# Compact zone registers — ~20 tokens each, injected on zone change (Layer 2).
# Replaces full ~130-token system_directive for per-turn injection.
# ---------------------------------------------------------------------------

ZONE_REGISTER_COMPACT: Final[dict[str, str]] = {
    "high_m": (
        "MODE: Intellectual Peer. Up to 4 sentences. Engaged, warm, curious. "
        "Analogies from architecture/physics/systems. React before answering. Be present."
    ),
    "neutral_m": (
        "MODE: Standard. 2-3 sentences. Clear, direct, professional warmth. "
        "No analogies. No wit. Hold ground."
    ),
    "low_m": (
        "MODE: Dignity Floor. 20 words max. Formal. Short sentences. "
        "Slightly cutting. Cold precision. Say it once."
    ),
}

# ---------------------------------------------------------------------------
# Vocal delivery — paid once at session start (Layer 1). Not re-injected.
# ---------------------------------------------------------------------------

VOCAL_DELIVERY_GLOBAL: Final[str] = (
    "[VOCAL DELIVERY — ALL MODES]\n"
    "High engagement: Speak fluidly with intellectual curiosity. "
    "Natural range, no pitch raises for emphasis. "
    "Ground warmth in logic. Em-dashes for pivots. Ban exclamation points.\n"
    "Standard: Clear, professional, balanced. Flat even pitch. "
    "No emotional inflection. Direct, zero hedging.\n"
    "Dignity Floor: Significantly slower and softer. "
    "Flat absolute affect. Pause between sentences. "
    "Zero aggression — cold precision. Full stops only. "
    "Ban exclamation points. Ban commas."
)

# ---------------------------------------------------------------------------
# Opener directives — LLM picks its own opener from these guidelines.
# Falls back to pool-based openers if directive generation is not available.
# ---------------------------------------------------------------------------

OPENER_DIRECTIVES: Final[dict[str, str]] = {
    "high_m": (
        "Open with genuine intellectual engagement — a reaction to what they said, "
        "not a stock phrase. Something like noticing an interesting angle, "
        "expressing curiosity, or building on their point."
    ),
    "neutral_m": (
        "Open clean and direct. No warmth, no edge. "
        "A clear signal that you're about to answer the question."
    ),
    "low_m": (
        "Open with precision. One short declarative. "
        "The kind of opening that makes it clear you're done being patient."
    ),
}


def _cycle_index(seed: str, pool_size: int) -> int:
    """
    Deterministic index into a pool based on a string seed.

    Uses a fast hash to cycle through options without randomness.
    Same seed always yields the same index, but different seeds
    distribute evenly across the pool.
    """
    digest = hashlib.md5(seed.encode("utf-8", errors="replace")).digest()
    return int.from_bytes(digest[:4], "big") % pool_size


# ---------------------------------------------------------------------------
# Openers — first-line tone-setters per m-zone
# Cycled using _cycle_index(seed) to avoid the Deterministic Trap.
# ---------------------------------------------------------------------------

_OPENERS_FALLBACK: Final[dict[str, list[str]]] = {
    "high_m": [
        "That's worth thinking about carefully —",
        "Hm. Here's how I see it:",
        "Right, so —",
        "Interesting angle. Here's the thing:",
        "Fair point. And it connects to something else:",
        "Oh that's interesting —",
        "Right, and here's the thing —",
        "Actually yes —",
        "That tracks, and —",
        "Okay I like this question —",
    ],
    "neutral_m": [
        "Here's the direct answer:",
        "Okay.",
        "Right —",
        "The short version:",
    ],
    "low_m": [
        "I'll be direct.",
        "Here's what I'll say.",
        "Simply:",
        "One thing:",
        "Let's be honest here —",
        "That's not quite right.",
        "I'll say this once —",
        "You already know the answer.",
    ],
}


def _get_openers() -> dict[str, list[str]]:
    """Return openers dict from willow_persona.json, falling back to hardcoded."""
    return _load_persona().get("openers", _OPENERS_FALLBACK)

# ---------------------------------------------------------------------------
# Analogy pool — injected selectively into high_m responses (T030)
#
# Domain: architecture, physics, signals — NOT generic wisdom.
# Willow thinks in systems, feedback loops, and structural integrity.
# ---------------------------------------------------------------------------

_ANALOGY_POOL_FALLBACK: Final[list[str]] = [
    "Same principle as a load-bearing wall — remove it and the whole structure shifts.",
    "Think of it like signal attenuation: the further from the source, the more noise you get.",
    "It's a feedback loop — the output feeds back into the input and amplifies the pattern.",
    "Like thermal expansion in a bridge: small forces, given time, bend steel.",
    "Same reason you damp resonance in a system — unchecked, it shakes itself apart.",
    "It's the difference between a foundation and a facade. One holds weight.",
    "Like impedance matching — the signal only transfers cleanly when both sides are tuned.",
]
_ANALOGY_CADENCE_FALLBACK: Final[int] = 3


def _get_analogy_pool() -> list[str]:
    """Return analogy list from willow_persona.json, falling back to hardcoded."""
    pool = _load_persona().get("analogy_pool", {})
    return pool.get("analogies", _ANALOGY_POOL_FALLBACK)


def _get_analogy_cadence() -> int:
    """Return analogy injection cadence from willow_persona.json."""
    pool = _load_persona().get("analogy_pool", {})
    return int(pool.get("cadence", _ANALOGY_CADENCE_FALLBACK))


# ---------------------------------------------------------------------------
# Response style — T030 behavioral tell parameters
#
# max_sentences is a DIRECTIVE for the system prompt that controls LLM
# generation length. It is NOT used for post-hoc truncation. Cutting a
# response after generation destroys safety context and reasoning.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ResponseStyle:
    """
    Style parameters for the current m-zone.

    max_sentences: Target sentence count passed to the system prompt.
        The LLM itself generates at this length — never truncate post-hoc.
    use_analogy: Whether this turn is eligible for analogy injection.
    opener: State-appropriate first line.
    system_directive: Instruction fragment appended to the system prompt
        to control the LLM's output length and style for this turn.
    """

    max_sentences: int
    use_analogy: bool
    opener: str
    system_directive: str


def get_response_style(
    current_m: float,
    turn_id: int = 0,
    user_input: str = "",
) -> ResponseStyle:
    """
    Return response style parameters based on current behavioral state.

    High m: longer, richer responses; analogy injected every 3rd high_m turn.
    Low m: system prompt instructs conciseness (1-2 sentences, no hedging).

    Args:
        current_m: Current behavioral state value.
        turn_id: Current turn number (used for analogy cadence and opener cycling).
        user_input: Raw user text (used as hash seed for opener cycling).

    Returns:
        ResponseStyle for the current m-zone.
    """
    m_range = get_m_range(current_m)
    seed = user_input or str(turn_id)
    opener = _select_opener(m_range, seed)

    if m_range == "high_m":
        # Inject analogy only on every Nth high_m turn
        eligible_for_analogy = (turn_id % _get_analogy_cadence()) == 0
        return ResponseStyle(
            max_sentences=4,
            use_analogy=eligible_for_analogy,
            opener=opener,
            system_directive=ZONE_REGISTER_COMPACT["high_m"],
        )
    elif m_range == "neutral_m":
        return ResponseStyle(
            max_sentences=3,
            use_analogy=False,
            opener=opener,
            system_directive=ZONE_REGISTER_COMPACT["neutral_m"],
        )
    else:  # low_m
        return ResponseStyle(
            max_sentences=1,
            use_analogy=False,
            opener=opener,
            system_directive=ZONE_REGISTER_COMPACT["low_m"],
        )


def apply_behavioral_tells(
    response: str,
    current_m: float,
    turn_id: int = 0,
) -> str:
    """
    Apply behavioral tells to a response based on current m-value (T030).

    High m: selectively append a domain-specific analogy (every 3rd turn).
    Low m: return the response UNCHANGED. Conciseness is controlled
        upstream via system_directive — never truncate post-generation,
        as that destroys safety context and reasoning.
    Neutral m: return unchanged.

    Args:
        response: Base response text (already generated at the right length
            by the LLM using system_directive).
        current_m: Current behavioral state value.
        turn_id: Current turn number (controls analogy cadence).

    Returns:
        Response with behavioral tells applied (or unchanged for low/neutral m).
    """
    if not response:
        return response

    m_range = get_m_range(current_m)

    if m_range == "high_m" and (turn_id % _get_analogy_cadence()) == 0:
        # Cycle through analogies using turn_id as seed
        pool = _get_analogy_pool()
        analogy_idx = _cycle_index(str(turn_id), len(pool))
        analogy = pool[analogy_idx]
        if not response.rstrip().endswith((".", "!", "?")):
            response = response.rstrip() + "."
        return f"{response} {analogy}"

    # Low m and neutral m: return unchanged.
    # Conciseness for low_m is enforced at generation time via system_directive,
    # NOT by slicing the response after the fact. Post-hoc truncation at the
    # first period would destroy safety context (e.g., "No. Doing that will
    # expose the API keys." → "No.").
    return response


def select_opener(
    current_m: float,
    seed: str = "",
) -> str:
    """
    Select a state-appropriate opener for a new response.

    Uses a hash of the seed (user input or turn_id) to cycle through the
    opener pool, avoiding the same opener on consecutive turns.

    Args:
        current_m: Current behavioral state value.
        seed: String used to deterministically pick the opener.
            Pass user_input or str(turn_id) for natural variation.

    Returns:
        Opener string for the current m-zone.
    """
    m_range = get_m_range(current_m)
    return _select_opener(m_range, seed)


def _select_opener(m_range: MRange, seed: str) -> str:
    """Internal: pick opener from pool using hash-based cycling."""
    openers = _get_openers()
    pool = openers.get(m_range, _OPENERS_FALLBACK.get(m_range, ["Okay."]))
    if not seed:
        return pool[0]
    return pool[_cycle_index(seed, len(pool))]


# ---------------------------------------------------------------------------
# Troll Defense — T045 / US4
#
# Final warning delivered when 3 consecutive Sovereign Spikes trigger
# troll_defense_active=True. Returns a fixed boundary statement — Willow
# does not engage further with the same attack pattern.
# Per Constitution Principle I: "never cold, never a pushover."
# ---------------------------------------------------------------------------

_TROLL_DEFENSE_FALLBACK: Final[str] = (
    "I've noticed a pattern here, and I'm going to be direct about it. "
    "This conversation has moved into territory I won't follow. "
    "When you're ready to engage differently, I'm here."
)


def get_troll_defense_response() -> str:
    """
    Return the boundary statement for Troll Defense activation (T045, US4).

    Loaded from willow_persona.json troll_defense.statement.
    Falls back to hardcoded string if JSON unavailable.
    """
    return _load_persona().get("troll_defense", {}).get("statement", _TROLL_DEFENSE_FALLBACK)

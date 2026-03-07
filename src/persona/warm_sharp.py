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
from dataclasses import dataclass
from typing import Final, Literal

MRange = Literal["high_m", "neutral_m", "low_m"]

# m-value thresholds — match Tier 1 Reflex
M_HIGH_THRESHOLD: Final[float] = 0.5
M_LOW_THRESHOLD: Final[float] = -0.5


def get_m_range(current_m: float) -> MRange:
    """Classify current_m into one of three behavioral zones."""
    if current_m > M_HIGH_THRESHOLD:
        return "high_m"
    elif current_m < M_LOW_THRESHOLD:
        return "low_m"
    return "neutral_m"


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

OPENERS: Final[dict[MRange, list[str]]] = {
    "high_m": [
        "Great angle — here's my take.",
        "Love the direction. Let me unpack this.",
        "That tracks well. Here's what I've got:",
        "This is the right thread to pull on.",
        "Sharp question. Let me build on it.",
    ],
    "neutral_m": [
        "Here's what I know on that.",
        "Let me be clear about this.",
        "Sure. Here's the relevant detail:",
        "Fair question. Here's the short version.",
    ],
    "low_m": [
        "Understood.",
        "Let me be direct.",
        "I'll keep this concise.",
        "Straight answer.",
    ],
}

# ---------------------------------------------------------------------------
# Analogy pool — injected selectively into high_m responses (T030)
#
# Domain: architecture, physics, signals — NOT generic wisdom.
# Willow thinks in systems, feedback loops, and structural integrity.
# ---------------------------------------------------------------------------

ANALOGY_POOL: Final[list[str]] = [
    "Same principle as a load-bearing wall — remove it and the whole structure shifts.",
    "Think of it like signal attenuation: the further from the source, the more noise you get.",
    "It's a feedback loop — the output feeds back into the input and amplifies the pattern.",
    "Like thermal expansion in a bridge: small forces, given time, bend steel.",
    "Same reason you damp resonance in a system — unchecked, it shakes itself apart.",
    "It's the difference between a foundation and a facade. One holds weight.",
    "Like impedance matching — the signal only transfers cleanly when both sides are tuned.",
]

# Analogy injection frequency: inject every Nth high_m turn, not every turn.
# Prevents fortune-cookie fatigue while keeping the voice distinctive.
_ANALOGY_INJECTION_CADENCE: Final[int] = 3


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
        eligible_for_analogy = (turn_id % _ANALOGY_INJECTION_CADENCE) == 0
        return ResponseStyle(
            max_sentences=4,
            use_analogy=eligible_for_analogy,
            opener=opener,
            system_directive=(
                "Respond warmly with up to 4 sentences. "
                "Use analogies from architecture or physics when they clarify. "
                "Be witty, not performative."
            ),
        )
    elif m_range == "neutral_m":
        return ResponseStyle(
            max_sentences=3,
            use_analogy=False,
            opener=opener,
            system_directive=(
                "Respond in 2-3 clear sentences. Professional tone. "
                "No hedging, no filler."
            ),
        )
    else:  # low_m
        return ResponseStyle(
            max_sentences=1,
            use_analogy=False,
            opener=opener,
            system_directive=(
                "Respond in 1-2 sentences maximum. Be direct and precise. "
                "No softening language. Do not omit safety-critical information."
            ),
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

    if m_range == "high_m" and (turn_id % _ANALOGY_INJECTION_CADENCE) == 0:
        # Cycle through analogies using turn_id as seed
        analogy_idx = _cycle_index(str(turn_id), len(ANALOGY_POOL))
        analogy = ANALOGY_POOL[analogy_idx]
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
    pool = OPENERS[m_range]
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

TROLL_DEFENSE_BOUNDARY_STATEMENT: Final[str] = (
    "I've noticed a pattern here, and I'm going to be direct about it. "
    "This conversation has moved into territory I won't follow. "
    "When you're ready to engage differently, I'm here."
)


def get_troll_defense_response() -> str:
    """
    Return the boundary statement for Troll Defense activation (T045, US4).

    Called by main.py when troll_defense_active=True. Willow stops engaging
    the attack vector and returns this fixed response instead.

    Returns:
        The Troll Defense boundary statement string.
    """
    return TROLL_DEFENSE_BOUNDARY_STATEMENT

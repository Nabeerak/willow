"""
Multi-session memory persistence.

Stores per-user behavioral state (M-value, turn count, rapport level,
key interactions) across sessions. Uses local JSON for development;
designed for easy swap to Firestore in production.

Schema per user:
    user_id: str
    sessions: list[SessionSummary]
    aggregate_m: float          # running M-value across sessions
    total_turns: int
    rapport_level: str          # "new" | "returning" | "trusted"
    last_seen: ISO timestamp
    user_name: str              # captured from first turn, persisted cross-session
"""

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

MEMORY_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "sessions"


# ---------------------------------------------------------------------------
# Name extraction — pattern matching only, no NLP dependency
# ---------------------------------------------------------------------------

_NAME_PATTERNS = [
    re.compile(r"\bI'?m\s+([A-Z][a-z]{1,20})\b"),
    re.compile(r"\bmy name(?:'s| is)\s+([A-Z][a-z]{1,20})\b", re.IGNORECASE),
    re.compile(r"\bthis is\s+([A-Z][a-z]{1,20})\b", re.IGNORECASE),
    re.compile(r"^([A-Z][a-z]{1,20})\s+here\b"),
]

# Words that look like names but aren't — exclude them from extraction
_COMMON_WORDS = frozenset([
    "Good", "Here", "Just", "Well", "Yes", "No", "Going", "Looking",
    "Working", "Trying", "Building", "Ready", "Back", "New", "There",
    "Not", "But", "So", "And", "The", "Okay", "Actually", "Basically",
    "Right", "Fine", "Sure", "Sorry", "Hey", "Hi", "Hello", "Willow",
])


def extract_user_context(transcript: str) -> tuple[str, str]:
    """
    Extract (user_name, topic_hint) from a transcript string.

    Name: matched via common intro patterns ("I'm X", "My name is X", etc.).
          Returns "" if no name detected or if the match is a common word.
    Topic: the transcript with the name introduction stripped, truncated to
           120 chars. Returns the full transcript if no name was found.

    Neither field is ever forced — both return "" when nothing was detected.
    """
    name = ""
    for pattern in _NAME_PATTERNS:
        m = pattern.search(transcript)
        if m:
            candidate = m.group(1)
            if candidate not in _COMMON_WORDS:
                name = candidate
                break

    # Topic hint: strip the name intro phrase and take the remainder
    topic = transcript.strip()
    if name:
        topic = re.sub(
            rf"(?:I'?m|my name(?:'s| is)|this is)\s+{re.escape(name)}[,.]?\s*",
            "",
            topic,
            flags=re.IGNORECASE,
        ).strip()
    topic = topic[:120]

    return name, topic


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class SessionSummary:
    session_id: str
    started_at: str
    ended_at: str
    turn_count: int
    final_m: float
    sovereign_triggers: list[str] = field(default_factory=list)
    pitch_avg_hz: int = 0


@dataclass
class UserMemory:
    user_id: str
    sessions: list[SessionSummary] = field(default_factory=list)
    aggregate_m: float = 0.6  # neutral start
    total_turns: int = 0
    rapport_level: str = "new"
    last_seen: str = ""
    user_name: str = ""  # captured from first turn; persisted cross-session

    def add_session(self, summary: SessionSummary) -> None:
        self.sessions.append(summary)
        self.total_turns += summary.turn_count
        # Exponential moving average of M across sessions
        alpha = 0.3
        self.aggregate_m = alpha * summary.final_m + (1 - alpha) * self.aggregate_m
        self.last_seen = summary.ended_at

        # Update rapport level based on session count
        n = len(self.sessions)
        if n >= 5:
            self.rapport_level = "trusted"
        elif n >= 2:
            self.rapport_level = "returning"
        else:
            self.rapport_level = "new"


class SessionMemoryStore:
    """Local JSON-backed session memory.

    Each user gets a JSON file at data/sessions/{user_id}.json.
    Thread-safe for single-process use (no concurrent writes expected).
    """

    def __init__(self, memory_dir: Optional[Path] = None):
        self._dir = memory_dir or MEMORY_DIR
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, user_id: str) -> Path:
        # Sanitize user_id for filesystem safety
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in user_id)
        return self._dir / f"{safe}.json"

    def load(self, user_id: str) -> UserMemory:
        path = self._path(user_id)
        if not path.exists():
            return UserMemory(user_id=user_id)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            sessions = [SessionSummary(**s) for s in data.get("sessions", [])]
            return UserMemory(
                user_id=data["user_id"],
                sessions=sessions,
                aggregate_m=data.get("aggregate_m", 0.6),
                total_turns=data.get("total_turns", 0),
                rapport_level=data.get("rapport_level", "new"),
                last_seen=data.get("last_seen", ""),
                user_name=data.get("user_name", ""),
            )
        except Exception as e:
            logger.error("Failed to load memory for %s: %s", user_id, e)
            return UserMemory(user_id=user_id)

    def save(self, memory: UserMemory) -> None:
        path = self._path(memory.user_id)
        try:
            data = {
                "user_id": memory.user_id,
                "sessions": [asdict(s) for s in memory.sessions],
                "aggregate_m": round(memory.aggregate_m, 4),
                "total_turns": memory.total_turns,
                "rapport_level": memory.rapport_level,
                "last_seen": memory.last_seen,
                "user_name": memory.user_name,
            }
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error("Failed to save memory for %s: %s", memory.user_id, e)

    def get_cold_start_m(self, user_id: str) -> float:
        """Get the initial M-value for a new session based on history.

        Returns aggregate_m for returning users, or 0.6 for new users.
        """
        memory = self.load(user_id)
        if memory.rapport_level == "new":
            return 0.6
        return memory.aggregate_m

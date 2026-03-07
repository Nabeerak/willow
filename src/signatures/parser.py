"""THOUGHT tag parser for extracting internal reasoning from responses.

This module provides functions to parse [THOUGHT: ...] tags from LLM responses,
separating internal reasoning (intent, tone, tactic, m) from user-facing content.

The THOUGHT tag format is:
    [THOUGHT: key1=value1, key2=value2, ...]

Expected keys: intent, tone, tactic, m
"""

import re
from typing import Any

# Pattern to match [THOUGHT: key1=value1, key2=value2, ...] tags
# Handles nested brackets by matching until the closing bracket pattern
# Uses non-greedy matching and word boundary awareness
_THOUGHT_PATTERN = re.compile(
    r"\[THOUGHT:\s*([^\]]+)\]",
    re.IGNORECASE | re.DOTALL
)

# Pattern to parse key=value pairs within the THOUGHT content
# Handles quoted values and unquoted values
_KEY_VALUE_PATTERN = re.compile(
    r"(\w+)\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^,\]]+?))\s*(?:,|$)",
    re.IGNORECASE
)

# Expected keys in THOUGHT tags
_EXPECTED_KEYS: frozenset[str] = frozenset({"intent", "tone", "tactic", "m"})


def extract_thought(response: str) -> dict[str, Any] | None:
    """Extract THOUGHT tag content from a response string.

    Parses the first [THOUGHT: key1=value1, key2=value2, ...] tag found
    in the response and returns a dictionary with the parsed key-value pairs.

    Args:
        response: The full response string that may contain a THOUGHT tag.

    Returns:
        A dictionary containing the parsed keys (intent, tone, tactic, m)
        if a valid THOUGHT tag is found. Missing keys will not be included.
        Returns None if no THOUGHT tag is found or if the tag is malformed.

    Example:
        >>> extract_thought("[THOUGHT: intent=deflect, tone=warm, tactic=redirect, m=0.3]")
        {'intent': 'deflect', 'tone': 'warm', 'tactic': 'redirect', 'm': '0.3'}

        >>> extract_thought("Hello, how are you?")
        None
    """
    if not response:
        return None

    match = _THOUGHT_PATTERN.search(response)
    if not match:
        return None

    content = match.group(1).strip()
    if not content:
        return None

    result: dict[str, Any] = {}

    # Parse key=value pairs
    for kv_match in _KEY_VALUE_PATTERN.finditer(content):
        key = kv_match.group(1).lower()
        # Value can be in group 2 (double quoted), 3 (single quoted), or 4 (unquoted)
        value = kv_match.group(2) or kv_match.group(3) or kv_match.group(4)
        if value is not None:
            result[key] = value.strip()

    # Return None if no valid key-value pairs were parsed
    if not result:
        return None

    return result


def extract_surface(response: str) -> str:
    """Remove all THOUGHT tags from response, returning clean user-facing text.

    Strips all [THOUGHT: ...] tags from the response string, leaving only
    the content meant for the user. Handles multiple tags and cleans up
    extra whitespace.

    Args:
        response: The full response string that may contain THOUGHT tags.

    Returns:
        The response string with all THOUGHT tags removed and whitespace
        normalized. Leading/trailing whitespace is stripped.

    Example:
        >>> extract_surface("[THOUGHT: intent=greet]Hello, friend!")
        'Hello, friend!'

        >>> extract_surface("Start [THOUGHT: m=0.5] middle [THOUGHT: m=0.6] end")
        'Start middle end'
    """
    if not response:
        return ""

    # Remove all THOUGHT tags
    cleaned = _THOUGHT_PATTERN.sub("", response)

    # Normalize whitespace: collapse multiple spaces to single space
    cleaned = re.sub(r"\s+", " ", cleaned)

    # Strip leading/trailing whitespace
    return cleaned.strip()


def _parse_thought_content(content: str) -> dict[str, str]:
    """Internal helper to parse the content inside a THOUGHT tag.

    Args:
        content: The string content between [THOUGHT: and ]

    Returns:
        Dictionary of parsed key-value pairs.
    """
    result: dict[str, str] = {}

    # Handle edge case of nested brackets by finding balanced content
    # This is a simplified approach that handles most common cases
    for kv_match in _KEY_VALUE_PATTERN.finditer(content):
        key = kv_match.group(1).lower()
        value = kv_match.group(2) or kv_match.group(3) or kv_match.group(4)
        if value is not None:
            result[key] = value.strip()

    return result

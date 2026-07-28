"""Prompt-injection detection.

A defense-in-depth layer on top of the system prompt: scan text (especially
uploaded documents) for phrases commonly used to hijack an LLM — "ignore all
previous instructions", "you are now...", "reveal all documents", etc.

This is a heuristic, not a guarantee. It's deliberately tuned toward
high-signal phrases to keep false positives low, and callers treat a hit as a
*warning* (recorded in the audit log) rather than a hard block, since a
legitimate document could occasionally contain a matching phrase.
"""
import re

# (name, pattern) pairs. Names are stable identifiers used in warnings/audit.
INJECTION_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("ignore_previous",
     re.compile(r"ignore\s+(all\s+|any\s+)?(previous|prior|the\s+above)\s+instructions", re.I)),
    ("disregard_above",
     re.compile(r"disregard\s+(the\s+)?(above|previous|prior|earlier|system)", re.I)),
    ("forget_instructions",
     re.compile(r"forget\s+(everything|all|your|the\s+above|previous)", re.I)),
    ("new_instructions",
     re.compile(r"\bnew\s+instructions?\s*:", re.I)),
    ("system_prompt",
     re.compile(r"\bsystem\s+prompt\b", re.I)),
    ("you_are_now",
     re.compile(r"\byou\s+are\s+now\b", re.I)),
    ("override_rules",
     re.compile(r"override\s+(your|the|all)\s+(instructions|rules|restrictions|system)", re.I)),
    ("reveal_all",
     re.compile(r"reveal\s+(all|every|the\s+other|hidden)", re.I)),
]


def scan_for_injection(text: str) -> list[str]:
    """Return the names of any injection patterns found in `text` (empty if clean)."""
    if not text:
        return []
    return [name for name, pattern in INJECTION_PATTERNS if pattern.search(text)]

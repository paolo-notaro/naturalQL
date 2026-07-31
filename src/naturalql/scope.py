"""Deterministic relevance checks for the demo's movie-data domain."""

import re

DOMAIN_TERMS = (
    "movie",
    "film",
    "cinema",
    "screening",
    "director",
    "actor",
    "person",
    "people",
    "cast",
    "role",
    "genre",
    "festival",
    "award",
    "release",
    "runtime",
    "box office",
    "title",
)

DOMAIN_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(term) for term in DOMAIN_TERMS) + r")(?:s|d)?\b",
    re.IGNORECASE,
)


def is_domain_question(question: str) -> bool:
    """Return whether a question explicitly refers to the available domain."""
    return bool(DOMAIN_RE.search(question))
